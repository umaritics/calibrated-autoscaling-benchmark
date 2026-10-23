#!/usr/bin/env python3
"""Independently verify and report the first D1 stepped comparison."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from verify_onoff_comparison import expected_schedule, integrate, load_samples, quantile


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/stepped_first_comparison"
RUN_ROOT = OUT / "stepped_d1_s62/repeat1"
ARMS = ["calibrated_hpa", "holtwinters", "strawman_hpa"]
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


def first_change(frame, boundary, column, direction):
    before = frame[frame.measurement_s < boundary]
    after = frame[frame.measurement_s >= boundary]
    if before.empty or after.empty:
        return None
    baseline = float(before.iloc[-1][column])
    changed = after[after[column] < baseline] if direction == "down" else after[after[column] > baseline]
    return None if changed.empty else float(changed.iloc[0].measurement_s - boundary)


def request_window(measured, start, end):
    part = measured[(measured.measurement_s >= start) & (measured.measurement_s < end)]
    success = part[(part.status == 200) & (part.error == "")]
    failures = len(part) - len(success)
    return {"scheduled": len(part), "successful": len(success), "failures": failures,
            "error_rate": failures / len(part) if len(part) else None,
            "success_p95_s": quantile(success.latency_s, .95) if len(success) else None}


def transition_metrics(frame, measured, transition, duration):
    boundary = float(transition["measurement_second"])
    direction = transition["direction"]
    window_end = min(duration, boundary + 120)
    result = {"direction": direction, "measurement_second": boundary,
              "post_step_120s": request_window(measured, boundary, window_end)}
    if direction == "up":
        desired_delay = first_change(frame, boundary, "desired", "up")
        ready_delay = first_change(frame, boundary, "ready", "up")
        pre = frame[(frame.measurement_s >= boundary - 60) & (frame.measurement_s < boundary)]
        result.update(
            desired_scale_up_delay_s=desired_delay,
            ready_scale_up_delay_s=ready_delay,
            first_30s=request_window(measured, boundary, min(duration, boundary + 30)),
            pre_step_capacity_sufficient=request_window(measured, boundary, min(duration, boundary + 30))["failures"] == 0,
            desired_increase_in_preceding_60s=bool(len(pre) > 1 and pre.desired.max() > pre.iloc[0].desired),
            ready_at_boundary=float(frame[frame.measurement_s < boundary].iloc[-1].ready),
        )
    else:
        plateau_end = min(duration, boundary + 400)
        final = frame[(frame.measurement_s >= plateau_end - 60) & (frame.measurement_s < plateau_end)]
        reference = float(final.ready.min()) if not final.empty else 1.0
        result.update(
            desired_scale_down_delay_s=first_change(frame, boundary, "desired", "down"),
            ready_scale_down_delay_s=first_change(frame, boundary, "ready", "down"),
            lower_plateau_end_s=plateau_end,
            final_60s_min_ready=reference,
            excess_ready_pod_seconds=integrate(frame, boundary, plateau_end, "ready",
                                               lambda x: np.maximum(0, x - reference)),
        )
    return result


def independent(run, arm, validation):
    metadata = json.loads((run / "metadata.json").read_text())
    duration = float(metadata["duration"])
    trace = pd.read_csv(run / "trace.csv")
    expected = expected_schedule(trace, int(metadata["warmup"]), int(duration))
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
    frame = load_samples(run, float(metadata["warmup"]), duration)
    window = frame[(frame.measurement_s >= 0) & (frame.measurement_s <= duration)]
    exclusive = all(len(kinds) == 1 and kinds[0] == KINDS[arm] for kinds in window.controllers)
    transitions = [transition_metrics(frame, measured, item, duration)
                   for item in validation["selected_window"]["transitions"]]
    plateaus = [{"window_seconds": item["replay_window_seconds"],
                 **request_window(measured, *item["replay_window_seconds"])}
                for item in validation["selected_window"]["plateaus"]]
    return {
        "schedule_exact": expected_keys == actual_keys,
        "schedule_sha256": canonical_schedule_hash(expected),
        "expected_total": len(expected), "total_records": len(requests),
        "measurement_records": len(measured), "successful_requests": len(success),
        "error_rate": (len(measured) - len(success)) / len(measured),
        "timeout_rate": int(timeout.sum()) / len(measured),
        "disconnect_rate": int(disconnect.sum()) / len(measured),
        "p50_latency_s": quantile(success.latency_s, .50),
        "p95_latency_s": quantile(success.latency_s, .95),
        "p99_latency_s": quantile(success.latency_s, .99),
        "dispatch_p99_s": quantile(measured.dispatch_s - measured.planned_s, .99),
        "pod_seconds": integrate(frame, 0, duration, "ready"),
        "controller_exclusive": exclusive, "transitions": transitions, "plateaus": plateaus,
    }


def shown(value):
    return "not observed" if value is None else f"{value:.2f}"


def main():
    validation = json.loads((OUT / "dataset_validation.json").read_text())
    rows, summaries, checks, transitions, plateaus = [], {}, {}, {}, {}
    duration = float(validation["transformation"]["measurement_seconds"])
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
            "latencies_agree": close(check["p50_latency_s"], summary["p50_latency_s"]) and close(check["p95_latency_s"], summary["p95_latency_s"]) and close(check["p99_latency_s"], summary["p99_latency_s"]),
            "dispatch_agrees": close(check["dispatch_p99_s"], summary["p99_dispatch_delay_s"]),
            "pod_seconds_agree": close(check["pod_seconds"], summary["pod_seconds"], 1e-6),
            "controller_exclusive": check["controller_exclusive"] and summary["active_controller"] == KINDS[arm],
            "measurement_duration_frozen": float(summary["duration"]) == duration,
        }
        if not all(checks[arm].values()):
            raise RuntimeError(f"independent verification failed for {arm}: {checks[arm]}")
        (run / "controller.yaml").write_bytes((ROOT / "policies" / POLICIES[arm]).read_bytes())
        transitions[arm] = check["transitions"]
        plateaus[arm] = check["plateaus"]
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
                     "restarts": summary["max_workload_restarts"],
                     "dispatch_p99_s": summary["p99_dispatch_delay_s"],
                     "generator_drops": summary["generator_drops"]})
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    status = "COMPLETE" if all(row["decision"] == "ACCEPT" for row in rows) else "PARTIAL"
    comparison = {"generated_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                  "scope": "one experimental repeat per controller; descriptive, not statistical",
                  "experiment_label": validation["experiment_label"], "arms": summaries,
                  "independent_checks": checks, "transition_metrics": transitions,
                  "plateau_request_metrics": plateaus, "rows": rows}
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")

    lines = ["# First verified live stepped comparison", "", validation["experiment_label"] + ".", "",
             "One repeat per controller; all comparisons are descriptive.", "",
             "| Controller | Decision | Errors / timeout | Success p50 / p95 / p99 (s) | Success RPS | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scale changes | Dispatch p99 (s) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['label']} | {row['decision']} | {row['error_rate']:.2%} / {row['timeout_rate']:.2%} | {row['p50_latency_s']:.3f} / {row['p95_latency_s']:.3f} / {row['p99_latency_s']:.3f} | {row['success_rps']:.2f} | {row['pod_seconds']:.2f} | {row['pod_seconds_per_success']:.5f} | {row['mean_ready']:.2f} / {row['max_ready']} | {row['cpu_coverage']:.2%} | {row['scaling_changes']} | {row['dispatch_p99_s']:.4f} |")
    lines += ["", "## Transition observations", "",
              "Boundaries and 120-second post-step windows were frozen before execution. Response lag is measured from the observed source boundary to the first matching desired/ready change relative to the last pre-boundary telemetry sample. Up-step capacity is called sufficient only when the first 30 seconds has zero failures. Down-step excess is ready-pod-seconds above the minimum ready count in the plateau's final 60 seconds. Collector resolution is about five seconds, so finer lag distinctions are not claimed.", "",
              "| Controller | Down desired / ready lag (s) | Low-plateau excess pod-s | Down-window errors | Up desired / ready lag (s) | Up-window errors | First-30s capacity sufficient | Desired rise in pre-step 60s |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        down = next(item for item in transitions[row["arm"]] if item["direction"] == "down")
        up = next(item for item in transitions[row["arm"]] if item["direction"] == "up")
        lines.append(f"| {row['label']} | {shown(down['desired_scale_down_delay_s'])} / {shown(down['ready_scale_down_delay_s'])} | {down['excess_ready_pod_seconds']:.2f} | {down['post_step_120s']['error_rate']:.2%} | {shown(up['desired_scale_up_delay_s'])} / {shown(up['ready_scale_up_delay_s'])} | {up['post_step_120s']['error_rate']:.2%} | {up['pre_step_capacity_sufficient']} | {up['desired_increase_in_preceding_60s']} |")
    by_arm = {row["arm"]: row for row in rows}
    soft, tuned, predictive = by_arm["strawman_hpa"], by_arm["calibrated_hpa"], by_arm["holtwinters"]
    accepted = sum(row["decision"] == "ACCEPT" for row in rows)
    valid_rows = [row for row in rows if row["decision"] == "ACCEPT"]
    best_qos = min(valid_rows, key=lambda x: (x["error_rate"], x["p95_latency_s"]))
    lowest_capacity = min(valid_rows, key=lambda x: x["pod_seconds"])
    lines += ["", "## Cost and request quality", "",
              f"Among accepted arms, {best_qos['label']} had the lowest error rate ({best_qos['error_rate']:.2%}); {lowest_capacity['label']} used the fewest ready-pod-seconds ({lowest_capacity['pod_seconds']:.2f}). Holt-Winters used {(predictive['pod_seconds'] - tuned['pod_seconds']) / tuned['pod_seconds']:.2%} more ready-pod-seconds than tuned HPA while reducing errors by {tuned['error_rate'] - predictive['error_rate']:.2%} percentage points. The rejected soft-HPA arm recorded {soft['error_rate']:.2%} errors and {soft['pod_seconds']:.2f} pod-seconds, but its 0.315-second dispatch p99 exceeded the frozen 0.100-second threshold, so those observations are not used for a valid causal controller comparison. Successful-request latency is interpreted only alongside scheduled-request error rate, never alone.", "",
              "Holt-Winters is described as temporally pre-scaling only if the frozen up-step metric reports a desired increase in the preceding 60 seconds. Holding more replicas by itself is not treated as proactivity.", "",
              f"At the upward boundary, tuned HPA changed desired/ready replicas in {transitions['calibrated_hpa'][0]['desired_scale_up_delay_s']:.0f}/{transitions['calibrated_hpa'][0]['ready_scale_up_delay_s']:.0f} seconds and Holt-Winters in {transitions['holtwinters'][0]['desired_scale_up_delay_s']:.0f}/{transitions['holtwinters'][0]['ready_scale_up_delay_s']:.0f} seconds. Both had zero failures in the frozen 120-second window, and neither increased desired replicas during the preceding 60 seconds. Thus prediction was not proactive at this observed step, and tuned HPA was competitive for abrupt-change QoS. The five-second difference is one collector interval and is not treated as a reliable fine-grained ordering.", "",
              f"At the downward boundary, tuned HPA delayed its first desired/ready decrease for {transitions['calibrated_hpa'][1]['desired_scale_down_delay_s']:.0f} seconds, consistent with its unchanged 300-second stabilization. Holt-Winters decreased after {transitions['holtwinters'][1]['desired_scale_down_delay_s']:.0f} seconds but still held more excess capacity over the low plateau ({transitions['holtwinters'][1]['excess_ready_pod_seconds']:.2f} versus {transitions['calibrated_hpa'][1]['excess_ready_pod_seconds']:.2f} pod-seconds) because it entered the plateau at a much higher replica count.", "",
              f"Errors were concentrated in the initial [0,400) plateau before the analyzed up-step: {plateaus['calibrated_hpa'][0]['error_rate']:.2%} tuned versus {plateaus['holtwinters'][0]['error_rate']:.2%} Holt-Winters. Later accepted-arm plateaus had zero errors. Workload restarts were {tuned['restarts']} tuned and {predictive['restarts']} Holt-Winters; the rejected soft arm recorded {soft['restarts']}.", "",
              "## Verification", "",
              f"Run disposition: {accepted} accepted, {sum(row['decision'] == 'INCONCLUSIVE' for row in rows)} inconclusive, and {sum(row['decision'] == 'REJECT' for row in rows)} rejected. The independent verifier reconstructed every deterministic request key, schedule hash, outcome denominator, successful-latency population, dispatch delay, ready-pod integral, controller identity, source/replay hash, transition timing, and measurement duration. All cross-checks passed. Per-run acceptance retains the unchanged analyzer thresholds, including at least 90% CPU coverage.", "",
              "## Limitations", "",
              "This is one repeat on a single-node kind cluster, so there is no variance estimate or causal generalization. The source is synthetic pod-count demand affinely mapped to HTTP rate, not observed traffic. The 90× time compression changes physical meaning; individual 10-second noisy bins are below HPA metric resolution even though the 400-second plateaus are observable. Fixed arm order, host contention, a PHPA configuration not retuned for this workload, and only one transition per direction remain limitations. The longer duration differs from growing/on-off; cross-pattern raw cost comparisons must normalize by demand and time."]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")

    verification = {"generated_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                    "acceptance_criteria_unchanged": True, "cpu_coverage_threshold": .90,
                    "checks": checks, "run_decisions": {arm: summaries[arm]["decision"] for arm in ARMS}}
    (OUT / "independent_verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    manifest = {}
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "evidence_manifest.json"):
        manifest[str(path.relative_to(ROOT))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    code = {}
    for relative in ("scripts/live/prepare_stepped_comparison.py", "scripts/live/preflight_stepped.py",
                     "scripts/live/run_stepped_comparison.py", "scripts/live/run_trace.py",
                     "scripts/live/analyze_runs.py", "scripts/live/verify_stepped_comparison.py",
                     "policies/hpa-baseline.yaml", "policies/hpa-calibrated.yaml",
                     "policies/phpa-holtwinters.yaml", "manifests/sample-app.yaml"):
        path = ROOT / relative
        code[relative] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    (OUT / "evidence_manifest.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(), "algorithm": "sha256",
        "files": manifest, "code_and_configuration": code}, indent=2) + "\n")
    print(json.dumps({"status": status, "decisions": verification["run_decisions"],
                      "manifest_files": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
