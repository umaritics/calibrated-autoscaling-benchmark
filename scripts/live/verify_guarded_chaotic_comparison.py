#!/usr/bin/env python3
"""Independently verify the guarded variant and close a blocked safety gate."""

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"


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


def main():
    plan = json.loads((OUT / "frozen_plan.json").read_text())
    trace_path = ROOT / plan["replay_path"]
    trace = pd.read_csv(trace_path)
    computed_schedule, measurement_count = schedule_hash(trace)
    resource = json.loads((OUT / "resource_budget.json").read_text())
    smoke = json.loads((OUT / "smoke_test_attempt3.json").read_text())
    smoke_run = OUT / "pilot_guarded_smoke/guarded_smoke/repeat3/calibrated_hpa"
    requests = list(csv.DictReader((smoke_run / "requests.csv").open()))
    measured = [row for row in requests if row["phase"] == "measurement"]
    independent_smoke_successes = sum(row["status"] == "200" and not row["error"] for row in measured)
    telemetry = [json.loads(line) for line in
                 (OUT / "smoke_watchdog_session_attempt3/host_pressure.jsonl").read_text().splitlines()]
    research_root = OUT / "chaotic_guarded_d1_s1"
    research_runs = list(research_root.rglob("summary.json")) if research_root.exists() else []
    checks = {
        "replay_hash_matches_frozen": digest(trace_path)["sha256"] == plan["replay_sha256"],
        "schedule_hash_matches_frozen": computed_schedule == plan["expected_schedule_sha256"],
        "measurement_count_matches_frozen": measurement_count == plan["transformation"]["scheduled_measurement_requests"] == 12532,
        "maximum_rate_is_45_rps": float(trace.target_rps.max()) == 45.0,
        "maximum_in_flight_is_256": plan["transformation"]["maximum_in_flight"] == 256,
        "balanced_order_frozen": plan["order"] == ["calibrated_hpa", "holtwinters", "strawman_hpa"],
        "kind_hard_limits_verified": resource["checks"]["docker_cgroup_limits_actual_match"],
        "preflight_passed": resource["decision"] == "PASS",
        "smoke_requests_independently_recomputed": len(measured) == independent_smoke_successes == 90,
        "smoke_watchdog_stayed_active": len(telemetry) >= 20,
        "smoke_gate_failed_as_recorded": smoke["decision"] == "FAIL" and
            not smoke["checks"]["generator_cgroup_limits_actual_match"],
        "failed_smoke_latches_orchestrator_block": (OUT / "SAFETY_GATE_BLOCK.json").exists(),
        "research_matrix_not_started_after_failed_gate": not research_runs,
    }
    pressure = {"samples": len(telemetry), "max_load1": max(row["load1"] for row in telemetry),
        "max_cpu_utilization_percent": max(row["cpu_utilization_percent"] for row in telemetry),
        "min_memory_available_bytes": min(row["memory_available_bytes"] for row in telemetry),
        "max_swap_used_bytes": max(row["swap_used_bytes"] for row in telemetry),
        "max_cpu_psi_some_avg10": max(row["cpu_psi_some_avg10"] for row in telemetry),
        "max_memory_psi_full_avg10": max(row["memory_psi_full_avg10"] for row in telemetry),
        "max_io_psi_full_avg10": max(row["io_psi_full_avg10"] for row in telemetry),
        "min_disk_free_bytes": min(row["disk_free_bytes"] for row in telemetry)}
    test = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=ROOT, capture_output=True, text=True)
    test_result = {"finished_utc": datetime.now(timezone.utc).isoformat(),
                   "command": [".venv/bin/python", "-m", "unittest", "discover", "-s", "tests", "-v"],
                   "returncode": test.returncode, "stdout": test.stdout, "stderr": test.stderr}
    (OUT / "focused_test_results.json").write_text(json.dumps(test_result, indent=2) + "\n")
    checks["full_test_suite_passed"] = test.returncode == 0
    dispositions = {"calibrated_hpa": "NOT_RUN_SAFETY_GATE", "holtwinters": "NOT_RUN_SAFETY_GATE",
                    "strawman_hpa": "NOT_RUN_SAFETY_GATE"}
    result = {"status": "BLOCKED", "reason": "SMOKE_RESOURCE_LIMIT_VERIFICATION_FAILED",
              "generated_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "host_pressure_smoke_attempt3": pressure, "run_dispositions": dispositions,
              "smoke_attempts": {"attempt1": "SAFETY_ABORTED_FALSE_POSITIVE_DURING_RESET",
                                 "attempt2": "FAIL_CPU_AFFINITY_NOT_OBSERVED_ALL_OTHER_CHECKS_PASS",
                                 "attempt3": "FAIL_SAME_LIMIT_VERIFICATION_AFTER_ATTEMPT2_COMPLETION_WAS_NOT_YET_VISIBLE_TO_CALLER"},
              "independent_smoke": {"measurement_records": len(measured),
                                    "successful_requests": independent_smoke_successes}}
    (OUT / "independent_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "comparison.json").write_text(json.dumps({"status": "BLOCKED", "rows": [],
        "reason": result["reason"], "run_dispositions": dispositions}, indent=2) + "\n")
    (OUT / "comparison.csv").write_text("arm,decision,error_rate,p95_latency_s,p99_latency_s,throughput_rps,pod_seconds,pod_seconds_per_success,mean_ready,max_ready,cpu_coverage,mean_cpu_m,max_cpu_m,scale_up_events,scale_down_events,replica_oscillations\n")
    (OUT / "FINDINGS.md").write_text(f"""# Guarded chaotic milestone findings

Status: **BLOCKED before research execution**.

The host/resource preflight passed and actual kind limits were verified (CPUs 0–3, 8 GiB RAM, zero swap, 4096 PIDs). The third smoke attempt sent all 90 low-intensity measurement requests successfully, retained {len(telemetry)} watchdog samples, and kept the host responsive: maximum load1 {pressure['max_load1']:.3f}, maximum CPU {pressure['max_cpu_utilization_percent']:.3f}%, minimum available RAM {pressure['min_memory_available_bytes']/1024**3:.3f} GiB, zero swap, and zero full memory/I/O PSI.

The generator scope proved its one-CPU quota, 768 MiB memory maximum, zero swap, and 512-task maximum. It did not expose the requested `cpuset.cpus.effective=4-5` value during the smoke, so the predeclared all-limits-match gate failed. No research arm was launched, no QoS/capacity/controller comparison is valid, and no retry or silent weakening occurred.

Smoke attempt 1 was safely aborted by a reset-phase false positive and preserved; the defect was fixed and explicitly resolved. Attempt 2 completed but its final result was not yet visible to the calling channel, so attempt 3 was started and independently produced the same limit-verification failure. Both are preserved; no research arm was retried or started.

The new 10–45 RPS variant remains frozen but unexecuted. It is not comparable as a replicate of the prior 20–120 RPS hazardous run and must never be pooled with it as n=2.
""")
    files = {}
    for path in sorted(item for item in OUT.rglob("*") if item.is_file() and item.name != "evidence_manifest.json"):
        files[str(path.relative_to(ROOT))] = digest(path)
    code_paths = ["configs/guarded_chaotic_safety.json", "scripts/live/safety_watchdog.py",
        "scripts/live/run_trace.py", "scripts/live/prepare_guarded_chaotic_comparison.py",
        "scripts/live/preflight_guarded_chaotic.py", "scripts/live/run_guarded_smoke.py",
        "scripts/live/run_guarded_chaotic_comparison.py", "scripts/live/verify_guarded_chaotic_comparison.py",
        "tests/test_safety_watchdog.py"]
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "algorithm": "sha256",
                "status": "BLOCKED", "files": files,
                "code_and_configuration": {path: digest(ROOT / path) for path in code_paths}}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "reason": result["reason"],
                      "checks_passed": sum(checks.values()), "checks_total": len(checks),
                      "tests_returncode": test.returncode}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
