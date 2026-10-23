#!/usr/bin/env python3
"""Independently verify and aggregate the NASA repetition milestone."""

import csv
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/nasa_three_repeat"
FIRST = ROOT / "results/live_trace_phase/first_comparison/nasa/repeat1"
NEW = OUT / "nasa"
ARMS = ["strawman_hpa", "calibrated_hpa", "holtwinters"]
LABELS = {"strawman_hpa": "Soft HPA (50%)", "calibrated_hpa": "Tuned HPA (70%)",
          "holtwinters": "Holt-Winters PHPA"}
KINDS = {"strawman_hpa": "HorizontalPodAutoscaler", "calibrated_hpa": "HorizontalPodAutoscaler",
         "holtwinters": "PredictiveHorizontalPodAutoscaler"}
POLICIES = {"strawman_hpa": "hpa-baseline.yaml", "calibrated_hpa": "hpa-calibrated.yaml",
            "holtwinters": "phpa-holtwinters.yaml"}
METRICS = ["error_rate", "timeout_rate", "p95_latency_s", "p99_latency_s", "success_rps",
           "pod_seconds", "mean_ready", "max_ready", "scaling_changes",
           "readiness_deficit_samples", "mean_cpu_m", "dispatch_p99_s",
           "pod_seconds_per_success"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_runs():
    paths = []
    for arm in ARMS:
        paths.append((1, arm, FIRST / arm))
    for repeat in (2, 3):
        for arm in ARMS:
            path = NEW / f"repeat{repeat}" / arm
            if path.exists():
                paths.append((repeat, arm, path))
    return paths


def all_attempts():
    result = accepted_runs()
    for path in sorted((NEW / "repeat3").glob("calibrated_hpa_inconclusive*")):
        result.append((3, "calibrated_hpa", path))
    return result


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


def independent(run, arm):
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
    controller_exclusive = all(len(controllers) == 1 and controllers[0] == KINDS[arm]
                               for elapsed, _, controllers in samples if start <= elapsed <= end)
    dispatch_delay = measured.dispatch_s - measured.planned_s
    return {
        "expected_total": len(expected), "total_records": len(requests),
        "measurement_records": len(measured), "schedule_exact": expected_keys == actual_keys,
        "successful_requests": len(success), "error_rate": (len(measured) - len(success)) / len(measured),
        "timeout_rate": int(timeout.sum()) / len(measured),
        "p95_latency_s": float(success.latency_s.quantile(.95)),
        "p99_latency_s": float(success.latency_s.quantile(.99)),
        "pod_seconds": pod_seconds, "controller_exclusive": controller_exclusive,
        "controller_kind": KINDS[arm] if controller_exclusive else None,
        "measurement_duration_s": end - start,
        "dispatch_p99_s": float(dispatch_delay.quantile(.99)),
    }


def close(left, right, tolerance=1e-8):
    return left is not None and right is not None and abs(float(left) - float(right)) <= tolerance


def sample_stats(values):
    values = [float(value) for value in values]
    return {"n": len(values), "mean": statistics.mean(values),
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    verified = []
    per_repeat = []
    for repeat, arm, run in all_attempts():
        summary = json.loads((run / "summary.json").read_text())
        check = independent(run, arm)
        verification = {
            "schedule_and_counts_agree": check["schedule_exact"] and
                check["expected_total"] == summary["scheduled_requests"] == check["total_records"] and
                check["measurement_records"] == summary["measurement_request_records"],
            "success_population_agrees": check["successful_requests"] == summary["successful_requests"],
            "error_rate_agrees": close(check["error_rate"], summary["error_rate"]),
            "timeout_rate_agrees": close(check["timeout_rate"], summary["timeouts"] / summary["measurement_request_records"]),
            "latencies_agree": close(check["p95_latency_s"], summary["p95_latency_s"]) and
                close(check["p99_latency_s"], summary["p99_latency_s"]),
            "pod_seconds_agree": close(check["pod_seconds"], summary["pod_seconds"], 1e-6),
            "duration_agrees": close(check["measurement_duration_s"], summary["intended_replay_duration_s"]),
            "controller_attribution_agrees": check["controller_exclusive"] and
                check["controller_kind"] == summary["active_controller"],
            "dispatch_p99_agrees": close(check["dispatch_p99_s"], summary["p99_dispatch_delay_s"]),
        }
        if not all(verification.values()):
            raise RuntimeError(f"independent verification failed for {run}: {verification}")
        policy = ROOT / "policies" / POLICIES[arm]
        (run / "controller.yaml").write_bytes(policy.read_bytes())
        relative = str(run.relative_to(ROOT))
        verified.append({"repeat": repeat, "arm": arm, "attempt": run.name,
                         "source_directory": relative, "analyzer_decision": summary["decision"],
                         "independent": check, "checks": verification})
        row = {
            "repeat": repeat, "arm": arm, "label": LABELS[arm], "attempt": run.name,
            "decision": summary["decision"], "source_directory": relative,
            "scheduled_measurement_requests": summary["scheduled_measurement_requests"],
            "successful_requests": summary["successful_requests"],
            "error_rate": summary["error_rate"],
            "timeout_rate": summary["timeouts"] / summary["scheduled_measurement_requests"],
            "p95_latency_s": summary["p95_latency_s"], "p99_latency_s": summary["p99_latency_s"],
            "success_rps": summary["achieved_success_rps"], "pod_seconds": summary["pod_seconds"],
            "mean_ready": summary["mean_ready"], "max_ready": summary["max_ready"],
            "scaling_changes": summary["scaling_changes"],
            "readiness_deficit_samples": summary["readiness_deficit_samples"],
            "mean_cpu_m": summary["mean_cpu_m"], "dispatch_p99_s": summary["p99_dispatch_delay_s"],
            "pod_seconds_per_success": summary["pod_seconds"] / summary["successful_requests"],
            "generator_drops": summary["generator_drops"], "cpu_sample_count": summary["cpu_sample_count"],
            "sample_count": summary["sample_count"],
        }
        per_repeat.append(row)

    accepted = [row for row in per_repeat if row["decision"] == "ACCEPT"]
    aggregates = []
    aggregate_json = {}
    for arm in ARMS:
        rows = [row for row in accepted if row["arm"] == arm]
        aggregate_json[arm] = {metric: sample_stats([row[metric] for row in rows]) for metric in METRICS}
        aggregate_json[arm]["accepted_repeats"] = [row["repeat"] for row in rows]
        for metric in METRICS:
            aggregates.append({"arm": arm, "label": LABELS[arm], "metric": metric,
                               **aggregate_json[arm][metric]})

    pairs = [("strawman_hpa", "holtwinters"), ("calibrated_hpa", "holtwinters"),
             ("strawman_hpa", "calibrated_hpa")]
    paired_rows = []
    paired_summary = []
    for left, right in pairs:
        for metric in ("error_rate", "timeout_rate", "p95_latency_s", "p99_latency_s",
                       "success_rps", "pod_seconds", "pod_seconds_per_success"):
            differences = []
            for repeat in (1, 2, 3):
                left_rows = [row for row in accepted if row["arm"] == left and row["repeat"] == repeat]
                right_rows = [row for row in accepted if row["arm"] == right and row["repeat"] == repeat]
                if left_rows and right_rows:
                    difference = left_rows[0][metric] - right_rows[0][metric]
                    differences.append(difference)
                    paired_rows.append({"comparison": f"{left}_minus_{right}", "repeat": repeat,
                                        "metric": metric, "difference": difference})
            stats = sample_stats(differences)
            paired_summary.append({"comparison": f"{left}_minus_{right}", "metric": metric, **stats})

    pd.DataFrame(per_repeat).sort_values(["repeat", "arm", "attempt"]).to_csv(OUT / "per_repeat.csv", index=False)
    pd.DataFrame(aggregates).to_csv(OUT / "mean_sd.csv", index=False)
    pd.DataFrame(paired_rows).to_csv(OUT / "paired_differences.csv", index=False)
    pd.DataFrame(paired_summary).to_csv(OUT / "paired_summary.csv", index=False)
    (OUT / "independent_verification.json").write_text(json.dumps(verified, indent=2) + "\n")
    matrix = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "status": "PARTIAL", "accepted_run_count": len(accepted),
              "attempt_count": len(per_repeat), "accepted_runs": accepted,
              "all_attempts": per_repeat, "aggregate": aggregate_json,
              "paired_summary": paired_summary,
              "limitation": "Repeat 3 tuned HPA remained INCONCLUSIVE after one unchanged retry because CPU telemetry was present in only 75/84 measurement samples."}
    (OUT / "nine_run_summary.json").write_text(json.dumps(matrix, indent=2) + "\n")

    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "runs": {}, "artifacts": {}}
    for _, _, run in all_attempts():
        key = str(run.relative_to(ROOT))
        manifest["runs"][key] = {path.name: {"path": str(path.relative_to(ROOT)),
                                                   "sha256": sha256(path), "bytes": path.stat().st_size}
                                        for path in sorted(run.iterdir()) if path.is_file()}
    for name in ("run_plan.json", "execution_ledger.jsonl", "checkpoint.json", "per_repeat.csv",
                 "mean_sd.csv", "paired_differences.csv", "paired_summary.csv",
                 "independent_verification.json", "nine_run_summary.json", "environment_metadata.json",
                 "PREFLIGHT.md", "REPRODUCE.md", "FINDINGS.md", "MILESTONE.md"):
        path = OUT / name
        if not path.exists():
            continue
        manifest["artifacts"][name] = {"path": str(path.relative_to(ROOT)),
                                            "sha256": sha256(path), "bytes": path.stat().st_size}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"accepted": len(accepted), "attempts": len(per_repeat),
                      "accepted_by_arm": {arm: len([row for row in accepted if row["arm"] == arm]) for arm in ARMS},
                      "all_independent_checks": all(all(item["checks"].values()) for item in verified)}, indent=2))


if __name__ == "__main__":
    main()
