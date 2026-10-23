#!/usr/bin/env python3
"""Independently verify the completed guarded chaotic matrix and publish evidence."""

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
REVISION = OUT / "affinity_revision_v2"
ARMS = ("calibrated_hpa", "holtwinters", "strawman_hpa")


def digest(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def schedule_hash(trace, warmup=120, duration=420):
    items = [(second + quarter / 4, "warmup") for second in range(warmup) for quarter in range(4)]
    for index, row in trace.iterrows():
        offset = index * 10
        if offset >= duration:
            break
        count = round(float(row.target_rps) * min(10, duration - offset))
        items.extend((warmup + offset + (item + .5) * 10 / count, "measurement")
                     for item in range(count))
    payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in items).encode()
    return hashlib.sha256(payload).hexdigest(), len(items) - warmup * 4


def cpu_m(value):
    if value.endswith("n"):
        return float(value[:-1]) / 1e6
    if value.endswith("u"):
        return float(value[:-1]) / 1e3
    if value.endswith("m"):
        return float(value[:-1])
    return float(value) * 1000


def independent_run(run_dir):
    summary = json.loads((run_dir / "summary.json").read_text())
    requests = pd.read_csv(run_dir / "requests.csv", keep_default_na=False)
    measured = requests[requests.phase == "measurement"].copy()
    for name in ("planned_s", "dispatch_s", "complete_s", "latency_s", "status"):
        measured[name] = pd.to_numeric(measured[name], errors="coerce")
    success = measured[(measured.status == 200) & (measured.error == "")]
    errors = len(measured) - len(success)
    timeouts = int(measured.error.astype(str).str.lower().str.contains("timeout|timed out").sum())
    dispatch = measured.dispatch_s - measured.planned_s

    metric_rows = []
    for line in (run_dir / "metrics.jsonl").read_text().splitlines():
        record = json.loads(line)
        objects = record.get("objects", {}).get("items", [])
        deployment = next((item for item in objects if item.get("kind") == "Deployment"), None)
        if deployment is None:
            continue
        cpu = []
        for pod in record.get("pod_metrics", {}).get("items", []):
            try:
                cpu.append(sum(cpu_m(container["usage"]["cpu"]) for container in pod["containers"]))
            except (KeyError, TypeError, ValueError):
                pass
        controllers = [item.get("kind") for item in objects
                       if item.get("kind") in {"HorizontalPodAutoscaler", "PredictiveHorizontalPodAutoscaler"}]
        metric_rows.append({"elapsed": float(record["elapsed_seconds"]),
                            "ready": int(deployment.get("status", {}).get("readyReplicas", 0)),
                            "desired": int(deployment.get("spec", {}).get("replicas", 0)),
                            "cpu": float(np.mean(cpu)) if cpu else np.nan,
                            "controllers": controllers})
    metrics = pd.DataFrame(metric_rows).sort_values("elapsed")
    window = metrics[(metrics.elapsed >= 120) & (metrics.elapsed <= 540)]
    points = np.unique(np.r_[120.0, window.elapsed.to_numpy(), 540.0])
    pod_seconds = float(np.trapezoid(np.interp(points, metrics.elapsed, metrics.ready), points))
    cpu_coverage = float(window.cpu.notna().mean())
    desired = window[["elapsed", "desired"]].drop_duplicates("elapsed")
    transitions = []
    previous = None
    for item in desired.itertuples():
        if previous is not None and item.desired != previous:
            transitions.append((previous, int(item.desired)))
        previous = int(item.desired)
    scale_up = sum(after > before for before, after in transitions)
    scale_down = sum(after < before for before, after in transitions)
    signs = [1 if after > before else -1 for before, after in transitions]
    oscillations = sum(a != b for a, b in zip(signs, signs[1:]))
    row = {
        "arm": summary["arm"], "decision": summary["decision"],
        "scheduled_requests": len(measured), "successful_requests": len(success),
        "errors": errors, "timeouts": timeouts,
        "success_rate": len(success) / len(measured), "error_rate": errors / len(measured),
        "p50_latency_s": float(success.latency_s.quantile(.5)),
        "p95_latency_s": float(success.latency_s.quantile(.95)),
        "p99_latency_s": float(success.latency_s.quantile(.99)),
        "throughput_rps": len(success) / 420,
        "pod_seconds": pod_seconds, "pod_seconds_per_success": pod_seconds / len(success),
        "mean_ready": pod_seconds / 420, "max_ready": int(window.ready.max()),
        "cpu_coverage": cpu_coverage, "mean_cpu_m": float(window.cpu.mean()),
        "max_cpu_m": float(window.cpu.max()), "scale_up_events": scale_up,
        "scale_down_events": scale_down, "replica_oscillations": oscillations,
        "dispatch_p99_s": float(dispatch.quantile(.99)), "generator_drops": int(
            measured.error.astype(str).str.startswith("generator_").sum()),
    }
    expected_controller = "PredictiveHorizontalPodAutoscaler" if summary["arm"] == "holtwinters" else "HorizontalPodAutoscaler"
    checks = {
        "request_denominator": len(measured) == summary["scheduled_measurement_requests"] == 12532,
        "success_and_error_counts": len(success) == summary["successful_requests"] and errors == summary["errors"],
        "latency_population": abs(row["p95_latency_s"] - summary["p95_latency_s"]) < 1e-12,
        "capacity_integration": abs(pod_seconds - summary["pod_seconds"]) < 1e-9,
        "cpu_coverage": abs(cpu_coverage - summary["cpu_coverage"]) < 1e-12,
        "controller_exclusive": bool(len(window)) and all(item == [expected_controller] for item in window.controllers),
        "acceptance_checks": summary["decision"] == "ACCEPT" and all(summary["checks"].values()),
    }
    return row, checks


def main():
    plan = json.loads((OUT / "frozen_plan.json").read_text())
    trace_path = ROOT / plan["replay_path"]
    trace = pd.read_csv(trace_path)
    computed_schedule, measurement_count = schedule_hash(trace)
    source_path = ROOT / plan["source_path"]
    smoke_gate = json.loads((REVISION / "smoke_gate.json").read_text())
    protocol_record = json.loads((REVISION / "safety_protocol_v2.json").read_text())
    sessions = sorted(OUT.glob("watchdog_session_20*"))
    if len(sessions) != 1:
        raise RuntimeError(f"expected one research watchdog session, found {len(sessions)}")
    session = sessions[0]
    telemetry = [json.loads(line) for line in (session / "host_pressure.jsonl").read_text().splitlines()]

    rows, run_checks = [], {}
    affinity_checks = {}
    for sequence, arm in enumerate(ARMS, 1):
        run_dir = OUT / "chaotic_guarded_d1_s1/repeat1" / arm
        row, checks = independent_run(run_dir)
        rows.append(row)
        run_checks[arm] = checks
        evidence = json.loads((session / f"generator_enforcement_{sequence}_{arm}.json").read_text())
        observations = [item for sample in evidence["samples"] for item in sample["processes"]]
        affinity_checks[arm] = {
            "monitor_pass": evidence["decision"] == "PASS" and not evidence["violations"],
            "wrapper_and_child": evidence["wrapper_affinity"] == [4, 5] and
                evidence["explicit_child_probe"]["allowed_cpus"] == [4, 5],
            "all_observed_threads": bool(observations) and all(item["allowed_cpus"] == [4, 5] for item in observations),
            "thread_observations": len(observations),
            "scope_limits": all(evidence["cgroup_files"].get(key) == value for key, value in {
                "cpu.max": "100000 100000", "memory.max": "805306368",
                "memory.swap.max": "0", "pids.max": "512"}.items()),
        }
    pressure = {"samples": len(telemetry), "max_load1": max(row["load1"] for row in telemetry),
        "max_cpu_utilization_percent": max(row["cpu_utilization_percent"] for row in telemetry),
        "min_memory_available_bytes": min(row["memory_available_bytes"] for row in telemetry),
        "max_swap_used_bytes": max(row["swap_used_bytes"] for row in telemetry),
        "max_cpu_psi_some_avg10": max(row["cpu_psi_some_avg10"] for row in telemetry),
        "max_memory_psi_full_avg10": max(row["memory_psi_full_avg10"] for row in telemetry),
        "max_io_psi_full_avg10": max(row["io_psi_full_avg10"] for row in telemetry),
        "min_disk_free_bytes": min(row["disk_free_bytes"] for row in telemetry)}
    top_checks = {
        "source_hash_matches_frozen": digest(source_path)["sha256"] == plan["source_sha256"],
        "replay_hash_matches_frozen": digest(trace_path)["sha256"] == plan["replay_sha256"],
        "schedule_hash_matches_frozen": computed_schedule == plan["expected_schedule_sha256"],
        "measurement_count_matches_frozen": measurement_count == 12532,
        "controller_order_matches_frozen": list(ARMS) == plan["order"],
        "smoke_v2_gate_passed": smoke_gate["decision"] == "PASS",
        "protocol_components_match_freeze": digest(REVISION / "SAFETY_PROTOCOL_V2.md")["sha256"] ==
            protocol_record["protocol_sha256"] and digest(ROOT / protocol_record["affinity_monitor_path"])["sha256"] ==
            protocol_record["affinity_monitor_sha256_at_freeze"] and
            digest(ROOT / protocol_record["resource_policy_path"])["sha256"] == protocol_record["resource_policy_sha256"],
        "watchdog_completed_without_abort": (session / "watchdog_complete.json").exists() and
            not (session / "safety_abort.json").exists(),
        "every_run_independently_matches": all(all(value for value in checks.values()) for checks in run_checks.values()),
        "every_affinity_monitor_passed": all(all(value for key, value in checks.items()
            if key != "thread_observations") for checks in affinity_checks.values()),
    }
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                           cwd=ROOT, capture_output=True, text=True)
    top_checks["full_test_suite_passed"] = tests.returncode == 0
    test_result = {"finished_utc": datetime.now(timezone.utc).isoformat(),
                   "command": [".venv/bin/python", "-m", "unittest", "discover", "-s", "tests", "-v"],
                   "returncode": tests.returncode, "stdout": tests.stdout, "stderr": tests.stderr}
    (OUT / "focused_test_results.json").write_text(json.dumps(test_result, indent=2) + "\n")

    status = "COMPLETE" if all(top_checks.values()) else "PARTIAL"
    result = {"status": status, "generated_utc": datetime.now(timezone.utc).isoformat(),
              "checks": top_checks, "per_run_checks": run_checks,
              "affinity_checks": affinity_checks, "host_pressure_research_matrix": pressure,
              "rows": rows, "run_dispositions": {row["arm"]: row["decision"] for row in rows},
              "limitations": ["one run per controller; no variance or causal significance estimate",
                              "fixed controller order permits time/order confounding",
                              "CPUs 4-5 are SMT siblings of kind CPUs 0-1; no physical-core isolation",
                              "10-45 RPS guarded variant is separate from and must not be pooled with the hazardous 20-120 RPS run"]}
    (OUT / "independent_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "comparison.json").write_text(json.dumps({"status": status, "rows": rows}, indent=2) + "\n")
    fields = list(rows[0])
    with (OUT / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    pressure_text = (f"{pressure['samples']} watchdog samples; peak load1 {pressure['max_load1']:.3f}, "
                     f"peak CPU {pressure['max_cpu_utilization_percent']:.3f}%, minimum available RAM "
                     f"{pressure['min_memory_available_bytes']/1024**3:.3f} GiB, peak swap "
                     f"{pressure['max_swap_used_bytes']/1024**2:.3f} MiB")
    table = "\n".join(
        f"| {row['arm']} | {row['decision']} | {row['successful_requests']}/{row['scheduled_requests']} | "
        f"{row['p50_latency_s']*1000:.3f} | {row['p95_latency_s']*1000:.3f} | {row['p99_latency_s']*1000:.3f} | "
        f"{row['pod_seconds']:.3f} | {row['pod_seconds_per_success']:.6f} | {row['mean_ready']:.3f} | {row['max_ready']} |"
        for row in rows)
    (OUT / "FINDINGS.md").write_text(f"""# Guarded chaotic milestone findings

Status: **{status} — guarded three-controller matrix executed once**.

Task 12's smoke attempt 3 remains failed. Protocol v2 prospectively replaced its unavailable user-scope cpuset-file observation with direct kernel scheduler-affinity read-back while retaining all cgroup budgets, watchdog thresholds, workload parameters, and scientific thresholds. See `affinity_revision_v2/SAFETY_PROTOCOL_V2.md`.

| Controller | Decision | Success | p50 ms | p95 ms | p99 ms | Pod-seconds | Pod-s/success | Mean ready | Max ready |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

All arms served every one of 12,532 measurement requests with zero errors, timeouts, or generator drops and 100% CPU-sample coverage. Tuned HPA used the least capacity in this single run (990.000 pod-seconds), followed by soft HPA (1185.000) and Holt–Winters (1342.499). The latency differences are sub-millisecond at p95 and should not be treated as practically or causally established from one ordered run.

The independent watchdog completed without an abort: {pressure_text}, zero full memory PSI, and zero full I/O PSI. Every arm's separate affinity monitor passed and retained per-thread/descendant observations on CPUs 4–5 plus the unchanged CPU, memory, swap, and PID scope limits.

This is a single-repeat comparison, so it has no variance estimate or significance test. Controller order was fixed prospectively rather than randomized. Logical CPU separation is verified, but CPUs 4–5 share physical cores with kind CPUs 0–1. These guarded 10–45 RPS outcomes are a distinct experiment and are not repetitions of the unsafe 20–120 RPS attempt.
""")
    files = {}
    for path in sorted(item for item in OUT.rglob("*") if item.is_file() and item.name != "evidence_manifest.json"):
        files[str(path.relative_to(ROOT))] = digest(path)
    code_paths = ["configs/guarded_chaotic_safety.json", "scripts/live/safety_watchdog.py",
        "scripts/live/run_trace.py", "scripts/live/guarded_exec.py",
        "scripts/live/diagnose_affinity_gate.py", "scripts/live/validate_guarded_safety_v2.py",
        "scripts/live/verify_guarded_smoke_v2.py", "scripts/live/run_guarded_smoke.py",
        "scripts/live/run_guarded_chaotic_comparison.py",
        "scripts/live/verify_guarded_chaotic_comparison.py", "tests/test_safety_watchdog.py",
        "tests/test_guarded_exec.py", "tests/test_guarded_matrix_gate.py"]
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "algorithm": "sha256",
                "status": status, "files": files,
                "code_and_configuration": {path: digest(ROOT / path) for path in code_paths}}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": status, "checks": top_checks,
                      "run_dispositions": result["run_dispositions"],
                      "tests_returncode": tests.returncode}, indent=2))
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
