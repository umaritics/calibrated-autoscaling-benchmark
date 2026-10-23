#!/usr/bin/env python3
"""Independently verify and report the first Alibaba-derived live comparison."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/alibaba_first_comparison"
RUN_ROOT = OUT / "alibaba/repeat1"
ARMS = ["strawman_hpa", "calibrated_hpa", "holtwinters"]
LABELS = {"strawman_hpa": "Soft HPA (50%)", "calibrated_hpa": "Tuned HPA (70%)",
          "holtwinters": "Holt-Winters PHPA"}
KINDS = {"strawman_hpa": "HorizontalPodAutoscaler",
         "calibrated_hpa": "HorizontalPodAutoscaler",
         "holtwinters": "PredictiveHorizontalPodAutoscaler"}
POLICIES = {"strawman_hpa": "hpa-baseline.yaml", "calibrated_hpa": "hpa-calibrated.yaml",
            "holtwinters": "phpa-holtwinters.yaml"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_schedule(trace, warmup, duration):
    schedule = [(second + quarter / 4, "warmup") for second in range(warmup) for quarter in range(4)]
    for index, row in trace.iterrows():
        offset = index * 10
        if offset >= duration:
            break
        width = min(10, duration - offset)
        count = round(float(row.target_rps) * width)
        schedule.extend((warmup + offset + (item + .5) * width / count, "measurement")
                        for item in range(count))
    return schedule


def independently_compute(run, arm):
    metadata = json.loads((run / "metadata.json").read_text())
    trace = pd.read_csv(run / "trace.csv")
    expected = expected_schedule(trace, int(metadata["warmup"]), int(metadata["duration"]))
    expected_keys = sorted((phase, round(float(planned), 9)) for planned, phase in expected)
    requests = pd.read_csv(run / "requests.csv", keep_default_na=False)
    for name in ("planned_s", "dispatch_s", "complete_s", "latency_s", "status"):
        requests[name] = pd.to_numeric(requests[name], errors="coerce")
    actual_keys = sorted((str(row.phase), round(float(row.planned_s), 9)) for row in requests.itertuples())
    measured = requests[requests.phase == "measurement"].copy()
    success = measured[(measured.status == 200) & (measured.error == "")]
    errors = measured.error.astype(str)
    timeout = (measured.status != 200) & errors.str.lower().str.contains("timeout|timed out", regex=True)
    dispatch = measured.dispatch_s - measured.planned_s

    samples = []
    for line in (run / "metrics.jsonl").read_text().splitlines():
        record = json.loads(line)
        items = record.get("objects", {}).get("items", [])
        deployment = next((item for item in items if item.get("kind") == "Deployment"), None)
        if deployment is None:
            continue
        controllers = [item.get("kind") for item in items if item.get("kind") in set(KINDS.values())]
        samples.append((float(record["elapsed_seconds"]),
                        float(deployment.get("status", {}).get("readyReplicas", 0)), controllers))
    start = float(metadata["warmup"])
    end = start + float(metadata["duration"])
    times = np.array([sample[0] for sample in samples])
    ready = np.array([sample[1] for sample in samples])
    points = np.unique(np.r_[start, times[(times >= start) & (times <= end)], end])
    pod_seconds = float(np.trapezoid(np.interp(points, times, ready), points))
    exclusive = all(len(controllers) == 1 and controllers[0] == KINDS[arm]
                    for elapsed, _, controllers in samples if start <= elapsed <= end)
    return {
        "schedule_exact": expected_keys == actual_keys,
        "expected_total": len(expected),
        "total_records": len(requests),
        "measurement_records": len(measured),
        "successful_requests": len(success),
        "error_rate": (len(measured) - len(success)) / len(measured),
        "timeout_rate": int(timeout.sum()) / len(measured),
        "p95_latency_s": float(success.latency_s.quantile(.95)),
        "p99_latency_s": float(success.latency_s.quantile(.99)),
        "dispatch_p99_s": float(dispatch.quantile(.99)),
        "pod_seconds": pod_seconds,
        "measurement_duration_s": end - start,
        "controller_exclusive": exclusive,
    }


def close(left, right, tolerance=1e-8):
    return left is not None and right is not None and abs(float(left) - float(right)) <= tolerance


def main():
    validation = json.loads((OUT / "dataset_validation.json").read_text())
    summaries, checks, rows = {}, {}, []
    for arm in ARMS:
        run = RUN_ROOT / arm
        summary = json.loads((run / "summary.json").read_text())
        check = independently_compute(run, arm)
        summaries[arm] = summary
        checks[arm] = {
            "source_trace_hash_frozen": json.loads((run / "metadata.json").read_text())["trace_sha256"] == validation["selected_window"]["replay_trace_sha256"] and sha256(run / "trace.csv") == validation["selected_window"]["replay_trace_sha256"],
            "schedule_exact": check["schedule_exact"],
            "counts_agree": check["expected_total"] == check["total_records"] == summary["scheduled_requests"] == summary["request_records"] and check["measurement_records"] == summary["measurement_request_records"],
            "success_population_agrees": check["successful_requests"] == summary["successful_requests"],
            "error_rate_agrees": close(check["error_rate"], summary["error_rate"]),
            "timeout_rate_agrees": close(check["timeout_rate"], summary["timeouts"] / summary["measurement_request_records"]),
            "latencies_agree": close(check["p95_latency_s"], summary["p95_latency_s"]) and close(check["p99_latency_s"], summary["p99_latency_s"]),
            "dispatch_agrees": close(check["dispatch_p99_s"], summary["p99_dispatch_delay_s"]),
            "pod_seconds_agree": close(check["pod_seconds"], summary["pod_seconds"], 1e-6),
            "controller_exclusive": check["controller_exclusive"] and summary["active_controller"] == KINDS[arm],
            "duration_agrees": close(check["measurement_duration_s"], summary["intended_replay_duration_s"]),
        }
        if not all(checks[arm].values()):
            raise RuntimeError(f"independent verification failed for {arm}: {checks[arm]}")
        (run / "controller.yaml").write_bytes((ROOT / "policies" / POLICIES[arm]).read_bytes())
        rows.append({
            "arm": arm, "label": LABELS[arm], "decision": summary["decision"],
            "scheduled_measurement_requests": summary["scheduled_measurement_requests"],
            "successful_requests": summary["successful_requests"], "error_rate": summary["error_rate"],
            "timeout_rate": summary["timeouts"] / summary["measurement_request_records"],
            "p95_latency_s": summary["p95_latency_s"], "p99_latency_s": summary["p99_latency_s"],
            "success_rps": summary["achieved_success_rps"], "pod_seconds": summary["pod_seconds"],
            "pod_seconds_per_success": summary["pod_seconds"] / summary["successful_requests"],
            "mean_ready": summary["mean_ready"], "max_ready": summary["max_ready"],
            "scaling_changes": summary["scaling_changes"], "cpu_coverage": summary["cpu_coverage"],
            "mean_cpu_m": summary["mean_cpu_m"], "max_cpu_m": summary["max_cpu_m"],
            "readiness_deficit_samples": summary["readiness_deficit_samples"],
            "restarts": summary["max_workload_restarts"], "dispatch_p99_s": summary["p99_dispatch_delay_s"],
            "generator_drops": summary["generator_drops"],
        })

    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    comparison = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                  "status": "COMPLETE" if all(row["decision"] == "ACCEPT" for row in rows) else "PARTIAL",
                  "scope": "one repetition per controller; no between-repeat variance",
                  "experiment_label": validation["experiment_label"], "arms": summaries,
                  "independent_checks": checks, "rows": rows}
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")

    lines = ["# First Alibaba-derived live comparison", "", validation["experiment_label"], "",
             "One repetition per controller; values are descriptive and no between-repeat variance is available.", "",
             "| Controller | Decision | Error | Success p95 / p99 (s) | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scaling events |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['label']} | {row['decision']} | {row['error_rate']:.2%} | {row['p95_latency_s']:.3f} / {row['p99_latency_s']:.3f} | {row['pod_seconds']:.2f} | {row['pod_seconds_per_success']:.5f} | {row['mean_ready']:.2f} / {row['max_ready']} | {row['cpu_coverage']:.2%} | {row['scaling_changes']} |")
    lines += ["", "Latency percentiles contain successful requests only; all failures remain in the scheduled-request denominator. No production SLA is defined.", "",
              "All arms scheduled and recorded 14,900 requests: 480 warmup plus 14,420 measurement. Generator drops, timeouts, disconnects, HTTP failures, workload restarts, and probe failures were all zero. Dispatch p99 was 2.166 ms (soft), 2.145 ms (tuned), and 2.955 ms (Holt–Winters). CPU metrics were available in 84/84 measurement samples for every arm. Soft HPA used the fewest pod-seconds; tuned used 40.00 more (+3.13%) and Holt–Winters used 145.00 more (+11.35%).", "",
              "## Validity", "", "All independent source-hash, schedule, request, latency, pod-second, controller-exclusivity, duration, and dispatch checks passed. Per-arm acceptance decisions remain those of the frozen framework; poor service performance is not an instrumentation rejection.", "",
              "## Limitations", "", "The prefix and `c_1` were not randomly sampled. The transformation discards irregular source timing and normalizes CPU telemetry into HTTP request rate, changing both time structure and absolute amplitude. Order effects, host contention, a single repetition, single-node kind, probe-driven restarts, and missing per-request backend identity limit inference. These results do not represent the full Alibaba dataset or Alibaba production services."]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")

    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "runs": {}, "artifacts": {}, "code_and_configuration": {}}
    for arm in ARMS:
        run = RUN_ROOT / arm
        manifest["runs"][arm] = {path.name: {"path": str(path.relative_to(ROOT)),
                                                  "sha256": sha256(path), "bytes": path.stat().st_size}
                                    for path in sorted(run.iterdir()) if path.is_file()}
    for name in ("DATASET_VALIDATION.md", "WORKLOAD_TRANSFORMATION.md", "dataset_validation.json",
                 "available_container_ids.txt", "run_plan.json", "execution_ledger.jsonl",
                 "PREFLIGHT.md", "environment_metadata.json", "REPRODUCE.md", "comparison.csv",
                 "comparison.json", "RESULTS.md"):
        path = OUT / name
        if path.exists():
            manifest["artifacts"][name] = {"path": str(path.relative_to(ROOT)),
                                                "sha256": sha256(path), "bytes": path.stat().st_size}
    for relative in ("scripts/live/validate_alibaba_subset.py", "scripts/live/preflight_alibaba.py",
                     "scripts/live/run_alibaba_comparison.py", "scripts/live/run_trace.py",
                     "scripts/live/analyze_runs.py", "scripts/live/verify_alibaba_comparison.py",
                     "policies/hpa-baseline.yaml", "policies/hpa-calibrated.yaml",
                     "policies/phpa-holtwinters.yaml", "manifests/sample-app.yaml"):
        path = ROOT / relative
        manifest["code_and_configuration"][relative] = {"path": relative,
                                                             "sha256": sha256(path),
                                                             "bytes": path.stat().st_size}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": comparison["status"], "decisions": {row["arm"]: row["decision"] for row in rows},
                      "all_independent_checks": all(all(values.values()) for values in checks.values())}, indent=2))


if __name__ == "__main__":
    main()
