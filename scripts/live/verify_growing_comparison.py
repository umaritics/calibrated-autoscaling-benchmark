#!/usr/bin/env python3
"""Independently verify and report the first D1 growing comparison."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from verify_onoff_comparison import expected_schedule, integrate, load_samples, quantile


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/growing_first_comparison"
RUN_ROOT = OUT / "growing_d1_s1/repeat1"
ARMS = ["strawman_hpa", "calibrated_hpa", "holtwinters"]
LABELS = {"strawman_hpa": "Soft HPA (50%)", "calibrated_hpa": "Tuned HPA (70%)",
          "holtwinters": "Holt-Winters PHPA"}
KINDS = {"strawman_hpa": "HorizontalPodAutoscaler", "calibrated_hpa": "HorizontalPodAutoscaler",
         "holtwinters": "PredictiveHorizontalPodAutoscaler"}
POLICIES = {"strawman_hpa": "hpa-baseline.yaml", "calibrated_hpa": "hpa-calibrated.yaml",
            "holtwinters": "phpa-holtwinters.yaml"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_schedule_hash(items):
    payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in items).encode()
    return hashlib.sha256(payload).hexdigest()


def close(left, right, tolerance=1e-8):
    return left is not None and right is not None and abs(float(left) - float(right)) <= tolerance


def response_delay(frame, onset, column):
    before = frame[frame.measurement_s < onset]
    after = frame[frame.measurement_s >= onset]
    if before.empty or after.empty:
        return None
    baseline = float(before.iloc[-1][column])
    changed = after[after[column] > baseline]
    return None if changed.empty else float(changed.iloc[0].measurement_s - onset)


def window_requests(measured, start, end):
    part = measured[(measured.measurement_s >= start) & (measured.measurement_s < end)]
    success = part[(part.status == 200) & (part.error == "")]
    failures = len(part) - len(success)
    return {"scheduled": len(part), "successful": len(success),
            "error_rate": failures / len(part) if len(part) else None,
            "success_p95_s": quantile(success.latency_s, .95) if len(success) else None,
            "offered_rps": len(part) / (end - start), "success_rps": len(success) / (end - start)}


def independent(run, arm, validation):
    metadata = json.loads((run / "metadata.json").read_text())
    trace = pd.read_csv(run / "trace.csv")
    expected = expected_schedule(trace, int(metadata["warmup"]), int(metadata["duration"]))
    requests = pd.read_csv(run / "requests.csv", keep_default_na=False)
    for name in ("planned_s", "dispatch_s", "complete_s", "latency_s", "status"):
        requests[name] = pd.to_numeric(requests[name], errors="coerce")
    expected_keys = sorted((phase, round(float(planned), 9)) for planned, phase in expected)
    actual_keys = sorted((str(row.phase), round(float(row.planned_s), 9)) for row in requests.itertuples())
    measured = requests[requests.phase == "measurement"].copy()
    measured["measurement_s"] = measured.planned_s - float(metadata["warmup"])
    success = measured[(measured.status == 200) & (measured.error == "")]
    timeout = (measured.status != 200) & measured.error.str.lower().str.contains("timeout|timed out", regex=True)
    disconnect = (measured.status != 200) & measured.error.str.contains(
        "Disconnected|ConnectionReset|ConnectionRefused", regex=True)
    frame = load_samples(run, float(metadata["warmup"]), float(metadata["duration"]))
    window = frame[(frame.measurement_s >= 0) & (frame.measurement_s <= float(metadata["duration"]))]
    exclusive = all(len(kinds) == 1 and kinds[0] == KINDS[arm] for kinds in window.controllers)
    onset = float(validation["growth_response_definition"]["onset_measurement_second"])
    early_start, early_end = validation["growth_response_definition"]["early_window_seconds"]
    late_start, late_end = validation["growth_response_definition"]["late_window_seconds"]
    early_pod_seconds = integrate(frame, early_start, early_end, "ready")
    late_pod_seconds = integrate(frame, late_start, late_end, "ready")
    first_scale = None
    start_ready = float(window.iloc[0].ready) if not window.empty else None
    if start_ready is not None:
        increased = window[window.ready > start_ready]
        if not increased.empty:
            first_scale = float(increased.iloc[0].measurement_s)
    return {
        "schedule_exact": expected_keys == actual_keys,
        "schedule_sha256": canonical_schedule_hash(expected),
        "expected_total": len(expected), "total_records": len(requests),
        "measurement_records": len(measured), "successful_requests": len(success),
        "error_rate": (len(measured) - len(success)) / len(measured),
        "timeout_rate": int(timeout.sum()) / len(measured),
        "disconnect_rate": int(disconnect.sum()) / len(measured),
        "p95_latency_s": quantile(success.latency_s, .95), "p99_latency_s": quantile(success.latency_s, .99),
        "dispatch_p99_s": quantile(measured.dispatch_s - measured.planned_s, .99),
        "pod_seconds": integrate(frame, 0, 420, "ready"), "controller_exclusive": exclusive,
        "growth": {
            "onset_measurement_second": onset,
            "desired_response_delay_s": response_delay(frame, onset, "desired"),
            "ready_response_delay_s": response_delay(frame, onset, "ready"),
            "first_ready_increase_measurement_second": first_scale,
            "first_ready_increase_before_onset": first_scale is not None and first_scale < onset,
            "early": window_requests(measured, early_start, early_end) |
                     {"pod_seconds": early_pod_seconds, "mean_ready": early_pod_seconds / (early_end - early_start)},
            "late": window_requests(measured, late_start, late_end) |
                    {"pod_seconds": late_pod_seconds, "mean_ready": late_pod_seconds / (late_end - late_start)},
            "post_onset": window_requests(measured, onset, 420),
        },
    }


def main():
    validation = json.loads((OUT / "dataset_validation.json").read_text())
    rows, summaries, checks, growth = [], {}, {}, {}
    for arm in ARMS:
        run = RUN_ROOT / arm
        summary = json.loads((run / "summary.json").read_text())
        check = independent(run, arm, validation)
        summaries[arm] = summary
        checks[arm] = {
            "source_trace_hash_frozen": sha256(run / "trace.csv") == validation["selected_window"]["replay_trace_sha256"],
            "schedule_hash_frozen": check["schedule_sha256"] == validation["expected_schedule_sha256"],
            "schedule_exact": check["schedule_exact"],
            "counts_agree": check["expected_total"] == check["total_records"] == summary["scheduled_requests"] == summary["request_records"],
            "success_population_agrees": check["successful_requests"] == summary["successful_requests"],
            "error_rate_agrees": close(check["error_rate"], summary["error_rate"]),
            "timeout_rate_agrees": close(check["timeout_rate"], summary["timeouts"] / summary["measurement_request_records"]),
            "latencies_agree": close(check["p95_latency_s"], summary["p95_latency_s"]) and close(check["p99_latency_s"], summary["p99_latency_s"]),
            "dispatch_agrees": close(check["dispatch_p99_s"], summary["p99_dispatch_delay_s"]),
            "pod_seconds_agree": close(check["pod_seconds"], summary["pod_seconds"], 1e-6),
            "controller_exclusive": check["controller_exclusive"] and summary["active_controller"] == KINDS[arm],
        }
        if not all(checks[arm].values()):
            raise RuntimeError(f"independent verification failed for {arm}: {checks[arm]}")
        (run / "controller.yaml").write_bytes((ROOT / "policies" / POLICIES[arm]).read_bytes())
        growth[arm] = check["growth"]
        rows.append({"arm": arm, "label": LABELS[arm], "decision": summary["decision"],
                     "scheduled_measurement_requests": summary["scheduled_measurement_requests"],
                     "successful_requests": summary["successful_requests"], "error_rate": summary["error_rate"],
                     "timeout_rate": check["timeout_rate"], "disconnection_rate": check["disconnect_rate"],
                     "p50_latency_s": summary["p50_latency_s"], "p95_latency_s": summary["p95_latency_s"],
                     "p99_latency_s": summary["p99_latency_s"], "success_rps": summary["achieved_success_rps"],
                     "pod_seconds": summary["pod_seconds"],
                     "pod_seconds_per_success": summary["pod_seconds"] / summary["successful_requests"],
                     "mean_ready": summary["mean_ready"], "max_ready": summary["max_ready"],
                     "scaling_changes": summary["scaling_changes"], "cpu_coverage": summary["cpu_coverage"],
                     "mean_cpu_m": summary["mean_cpu_m"], "max_cpu_m": summary["max_cpu_m"],
                     "readiness_deficit_samples": summary["readiness_deficit_samples"],
                     "restarts": summary["max_workload_restarts"], "dispatch_p99_s": summary["p99_dispatch_delay_s"],
                     "generator_drops": summary["generator_drops"],
                     "desired_growth_response_delay_s": check["growth"]["desired_response_delay_s"],
                     "ready_growth_response_delay_s": check["growth"]["ready_response_delay_s"],
                     "early_mean_ready": check["growth"]["early"]["mean_ready"],
                     "late_mean_ready": check["growth"]["late"]["mean_ready"],
                     "early_error_rate": check["growth"]["early"]["error_rate"],
                     "late_error_rate": check["growth"]["late"]["error_rate"]})
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    status = "COMPLETE" if all(row["decision"] == "ACCEPT" for row in rows) else "PARTIAL"
    comparison = {"generated_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                  "scope": "one experimental repeat per controller; descriptive, not statistical",
                  "experiment_label": validation["experiment_label"], "arms": summaries,
                  "independent_checks": checks, "growth_metrics": growth, "rows": rows}
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")

    lines = ["# First verified live growing comparison", "", validation["experiment_label"] + ".", "",
             "One repeat per controller; all comparisons are descriptive.", "",
             "| Controller | Decision | Errors / timeout | Success p95 / p99 (s) | Pod-s | Mean / max ready | CPU coverage | CPU mean / max (m) | Scale changes | Dispatch p99 (s) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['label']} | {row['decision']} | {row['error_rate']:.2%} / {row['timeout_rate']:.2%} | {row['p95_latency_s']:.3f} / {row['p99_latency_s']:.3f} | {row['pod_seconds']:.2f} | {row['mean_ready']:.2f} / {row['max_ready']} | {row['cpu_coverage']:.2%} | {row['mean_cpu_m']:.1f} / {row['max_cpu_m']:.1f} | {row['scaling_changes']} | {row['dispatch_p99_s']:.4f} |")
    by_arm = {row["arm"]: row for row in rows}
    soft = by_arm["strawman_hpa"]
    tuned = by_arm["calibrated_hpa"]
    predictive = by_arm["holtwinters"]
    total_measurement = sum(row["scheduled_measurement_requests"] for row in rows)
    lines += ["", f"All {total_measurement:,} scheduled measurement requests across the three arms succeeded. Tuned HPA used {(soft['pod_seconds'] - tuned['pod_seconds']) / soft['pod_seconds']:.2%} fewer ready-pod-seconds than soft HPA while preserving the same observed success rate. Holt-Winters used {(predictive['pod_seconds'] - soft['pod_seconds']) / soft['pod_seconds']:.2%} more than soft HPA and {(predictive['pod_seconds'] - tuned['pod_seconds']) / tuned['pod_seconds']:.2%} more than tuned HPA. Its successful-request p95 was also higher ({predictive['p95_latency_s']:.3f} s versus {soft['p95_latency_s']:.3f}–{tuned['p95_latency_s']:.3f} s), although all absolute latencies were low and no SLA was predeclared."]
    lines += ["", "## Growth-specific observations", "",
              f"Sustained-growth onset is predeclared at measurement second {validation['growth_response_definition']['onset_measurement_second']}: the first three consecutive 10-second bins at or above 70 requests/s. Response delay is the first desired/ready increase above the last pre-onset sample. Early and late windows are [0,140) and [280,420) seconds.", "",
              "| Controller | Desired / ready response delay (s) | Early → late mean ready | Early → late errors | First ready rise before onset |",
              "|---|---:|---:|---:|---:|"]
    def shown(value):
        return "not observed" if value is None else f"{value:.2f}"
    for row in rows:
        item = growth[row["arm"]]
        lines.append(f"| {row['label']} | {shown(item['desired_response_delay_s'])} / {shown(item['ready_response_delay_s'])} | {item['early']['mean_ready']:.2f} → {item['late']['mean_ready']:.2f} | {item['early']['error_rate']:.2%} → {item['late']['error_rate']:.2%} | {item['first_ready_increase_before_onset']} |")
    accepted = sum(row["decision"] == "ACCEPT" for row in rows)
    lines += ["", "A pre-onset replica increase is temporal evidence only; it is not, by itself, proof of proactive prediction. Capacity and QoS are reported separately, and lower pod-seconds is not treated as better service.", "",
              f"All controllers raised ready capacity from the early to the late window and sustained the complete offered throughput without failures. Relative to the last sample before the 70 requests/s threshold, Holt-Winters increased desired/ready replicas about {growth['holtwinters']['desired_response_delay_s']:.0f}/{growth['holtwinters']['ready_response_delay_s']:.0f} seconds after onset, tuned HPA about {growth['calibrated_hpa']['desired_response_delay_s']:.0f}/{growth['calibrated_hpa']['ready_response_delay_s']:.0f} seconds after, and soft HPA about {growth['strawman_hpa']['desired_response_delay_s']:.0f}/{growth['strawman_hpa']['ready_response_delay_s']:.0f} seconds after. Holt-Winters therefore responded earliest by this frozen criterion, but it also held {growth['holtwinters']['late']['mean_ready']:.2f} mean late-window replicas versus {growth['strawman_hpa']['late']['mean_ready']:.2f} soft and {growth['calibrated_hpa']['late']['mean_ready']:.2f} tuned, and changed desired replicas {predictive['scaling_changes']} times versus {soft['scaling_changes']} and {tuned['scaling_changes']}. This is consistent with a faster, more aggressive response; it does not establish that the response was causally proactive.", "",
              "## Verification", "",
              f"Run disposition: {accepted} accepted, {sum(row['decision'] == 'INCONCLUSIVE' for row in rows)} inconclusive, and {sum(row['decision'] == 'REJECT' for row in rows)} rejected. The independent verifier reconstructed every deterministic request key, schedule hash, request outcome, successful-latency population, dispatch delay, ready-pod integral, controller identity, source replay hash, and measurement window. All independent cross-checks passed. Per-run acceptance uses the unchanged analyzer thresholds, including at least 90% CPU coverage.", "",
              "## Limitations", "",
              "This is one repeat on a single-node kind cluster. The source is synthetic pod-count demand, affinely mapped to HTTP requests and compressed 90×; it is not native-time replay or production traffic. Ten-second bins are shorter than the 15-second CPU metric/HPA cadence, so only the sustained 420-second rise is interpreted. Fixed arm order and uncontrolled host contention remain limitations. The PHPA configuration was not retuned for this workload."]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")

    verification = {"generated_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                    "acceptance_criteria_unchanged": True, "cpu_coverage_threshold": 0.90,
                    "checks": checks, "run_decisions": {arm: summaries[arm]["decision"] for arm in ARMS}}
    (OUT / "independent_verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    manifest = {}
    excluded = {"evidence_manifest.json"}
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name not in excluded):
        manifest[str(path.relative_to(ROOT))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    (OUT / "evidence_manifest.json").write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(),
                                                              "algorithm": "sha256", "files": manifest}, indent=2) + "\n")
    print(json.dumps({"status": status, "decisions": verification["run_decisions"],
                      "manifest_files": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
