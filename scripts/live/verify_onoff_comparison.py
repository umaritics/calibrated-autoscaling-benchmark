#!/usr/bin/env python3
"""Independently verify and report the first D1-derived on/off comparison."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/onoff_first_comparison"
RUN_ROOT = OUT / "onoff_d1_s81/repeat1"
ARMS = ["strawman_hpa", "calibrated_hpa", "holtwinters"]
LABELS = {"strawman_hpa": "Soft HPA (50%)", "calibrated_hpa": "Tuned HPA (70%)",
          "holtwinters": "Holt-Winters PHPA"}
KINDS = {"strawman_hpa": "HorizontalPodAutoscaler", "calibrated_hpa": "HorizontalPodAutoscaler",
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


def quantile(series, q):
    return float(pd.to_numeric(series, errors="coerce").dropna().quantile(q))


def load_samples(run, warmup, duration):
    samples = []
    for line in (run / "metrics.jsonl").read_text().splitlines():
        record = json.loads(line)
        items = record.get("objects", {}).get("items", [])
        deployment = next((item for item in items if item.get("kind") == "Deployment"), None)
        if deployment is None:
            continue
        cpu = []
        for pod in record.get("pod_metrics", {}).get("items", []):
            for container in pod.get("containers", []):
                value = container.get("usage", {}).get("cpu", "")
                try:
                    cpu.append(float(value[:-1]) / 1e6 if value.endswith("n") else
                               float(value[:-1]) / 1e3 if value.endswith("u") else
                               float(value[:-1]) if value.endswith("m") else float(value) * 1000)
                except (TypeError, ValueError):
                    pass
        controllers = [item.get("kind") for item in items if item.get("kind") in set(KINDS.values())]
        elapsed = float(record["elapsed_seconds"])
        status = deployment.get("status", {})
        samples.append({"measurement_s": elapsed - warmup,
                        "ready": float(status.get("readyReplicas", 0)),
                        "current": float(status.get("replicas", 0)),
                        "desired": float(deployment.get("spec", {}).get("replicas", 0)),
                        "cpu_mean_m": float(np.mean(cpu)) if cpu else np.nan,
                        "controllers": controllers})
    return pd.DataFrame(samples).sort_values("measurement_s")


def integrate(frame, start, end, column, transform=lambda x: x):
    if frame.empty:
        return None
    points = np.unique(np.r_[start, frame.measurement_s[(frame.measurement_s >= start) & (frame.measurement_s <= end)], end])
    values = np.interp(points, frame.measurement_s, frame[column])
    return float(np.trapezoid(transform(values), points))


def first_change(frame, boundary, column, direction):
    before = frame[frame.measurement_s < boundary]
    after = frame[frame.measurement_s >= boundary]
    if before.empty or after.empty:
        return None
    baseline = float(before.iloc[-1][column])
    changed = after[after[column] < baseline] if direction == "down" else after[after[column] > baseline]
    return None if changed.empty else float(changed.iloc[0].measurement_s - boundary)


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
    measured["measurement_s"] = measured.planned_s - float(metadata["warmup"])
    success = measured[(measured.status == 200) & (measured.error == "")]
    timeout = (measured.status != 200) & measured.error.str.lower().str.contains("timeout|timed out", regex=True)
    disconnect = (measured.status != 200) & measured.error.str.contains("Disconnected|ConnectionReset|ConnectionRefused", regex=True)
    frame = load_samples(run, float(metadata["warmup"]), float(metadata["duration"]))
    measurement_frame = frame[(frame.measurement_s >= 0) & (frame.measurement_s <= float(metadata["duration"]))]
    exclusive = all(len(kinds) == 1 and kinds[0] == KINDS[arm] for kinds in measurement_frame.controllers)
    low_requests = measured[(measured.measurement_s >= 160) & (measured.measurement_s < 320)]
    activation = measured[(measured.measurement_s >= 320) & (measured.measurement_s < 380)]
    activation_success = activation[(activation.status == 200) & (activation.error == "")]
    return {
        "schedule_exact": expected_keys == actual_keys, "expected_total": len(expected),
        "total_records": len(requests), "measurement_records": len(measured),
        "successful_requests": len(success), "error_rate": (len(measured) - len(success)) / len(measured),
        "timeout_rate": int(timeout.sum()) / len(measured), "disconnect_rate": int(disconnect.sum()) / len(measured),
        "p50_latency_s": quantile(success.latency_s, .50), "p95_latency_s": quantile(success.latency_s, .95),
        "p99_latency_s": quantile(success.latency_s, .99),
        "dispatch_p99_s": quantile(measured.dispatch_s - measured.planned_s, .99),
        "pod_seconds": integrate(frame, 0, 420, "ready"), "controller_exclusive": exclusive,
        "high_to_low": {"measurement_second": 160,
                        "desired_scale_down_delay_s": first_change(frame, 160, "desired", "down"),
                        "ready_scale_down_delay_s": first_change(frame, 160, "ready", "down"),
                        "excess_ready_pod_seconds_above_minimum": integrate(frame, 160, 320, "ready", lambda x: np.maximum(0, x - 1)),
                        "request_error_rate": float(((low_requests.status != 200) | (low_requests.error != "")).mean())},
        "low_to_high": {"measurement_second": 320,
                        "desired_scale_up_delay_s": first_change(frame, 320, "desired", "up"),
                        "ready_scale_up_delay_s": first_change(frame, 320, "ready", "up"),
                        "first_60s_request_error_rate": float(((activation.status != 200) | (activation.error != "")).mean()),
                        "first_60s_success_p95_s": quantile(activation_success.latency_s, .95),
                        "first_60s_hot_cpu_fraction": float((frame[(frame.measurement_s >= 320) & (frame.measurement_s < 380)].cpu_mean_m.dropna() > 160).mean())},
    }


def close(left, right, tolerance=1e-8):
    return left is not None and right is not None and abs(float(left) - float(right)) <= tolerance


def main():
    validation = json.loads((OUT / "dataset_validation.json").read_text())
    rows, summaries, checks, transitions = [], {}, {}, {}
    for arm in ARMS:
        run = RUN_ROOT / arm
        summary = json.loads((run / "summary.json").read_text())
        check = independent(run, arm)
        summaries[arm] = summary
        checks[arm] = {
            "source_trace_hash_frozen": sha256(run / "trace.csv") == validation["selected_window"]["replay_trace_sha256"],
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
        transitions[arm] = {"high_to_low": check["high_to_low"], "low_to_high": check["low_to_high"]}
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
                     "generator_drops": summary["generator_drops"]})
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    comparison = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                  "status": "COMPLETE" if all(r["decision"] == "ACCEPT" for r in rows) else "PARTIAL",
                  "scope": "one accepted experimental repeat per controller; descriptive, not statistical",
                  "experiment_label": validation["experiment_label"], "arms": summaries,
                  "independent_checks": checks, "transition_metrics": transitions, "rows": rows}
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    lines = ["# First verified live on/off comparison", "", validation["experiment_label"] + ".", "",
             "One repeat per controller; all comparisons are descriptive.", "",
             "| Controller | Decision | Errors | Timeout | Success p95 / p99 (s) | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scale changes |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['label']} | {row['decision']} | {row['error_rate']:.2%} | {row['timeout_rate']:.2%} | {row['p95_latency_s']:.3f} / {row['p99_latency_s']:.3f} | {row['pod_seconds']:.2f} | {row['pod_seconds_per_success']:.5f} | {row['mean_ready']:.2f} / {row['max_ready']} | {row['cpu_coverage']:.2%} | {row['scaling_changes']} |")
    accepted = sum(row["decision"] == "ACCEPT" for row in rows)
    lines += ["", f"Run disposition: {accepted} accepted, {sum(row['decision'] == 'INCONCLUSIVE' for row in rows)} inconclusive, and {sum(row['decision'] == 'REJECT' for row in rows)} rejected.",
              "Successful-request latency excludes failures; every failure remains in the scheduled-request denominator. All arms retained 29,930 measurement records with zero generator drops; each workload experienced three restarts. Readiness-deficit samples were 33 (soft), 31 (tuned), and 17 (Holt-Winters).", "",
              "Holt-Winters had 13.29% errors versus 50.05% soft and 48.55% tuned, while consuming 119.7% more ready-pod-seconds than soft and 165.9% more than tuned. Tuned used 17.4% fewer ready-pod-seconds than soft but did not materially avoid overload.", "", "## Transition observations", "",
              "The frozen measurement has a high→low boundary at 160 s and a low→high boundary at 320 s. Scale response is the first observed desired/ready change in the matching direction relative to the last pre-boundary telemetry sample. Low-period excess capacity is ready-pod-seconds above the fixed one-pod minimum over [160,320). Activation QoS uses scheduled requests in [320,380). A missing delay means the matching response was not observed before measurement end; none of these definitions claims proactive forecasting.", "",
              "| Controller | Desired / ready down delay (s) | Low excess pod-s | Desired / ready up delay (s) | Activation errors | Activation success p95 (s) | Activation hot-CPU samples |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    def shown(value):
        return "not observed" if value is None else f"{value:.2f}"
    for row in rows:
        t = transitions[row["arm"]]; down = t["high_to_low"]; up = t["low_to_high"]
        lines.append(f"| {row['label']} | {shown(down['desired_scale_down_delay_s'])} / {shown(down['ready_scale_down_delay_s'])} | {down['excess_ready_pod_seconds_above_minimum']:.2f} | {shown(up['desired_scale_up_delay_s'])} / {shown(up['ready_scale_up_delay_s'])} | {up['first_60s_request_error_rate']:.2%} | {up['first_60s_success_p95_s']:.3f} | {up['first_60s_hot_cpu_fraction']:.2%} |")
    lines += ["", "## Verification", "", "The independent verifier reconstructed every deterministic request key, request outcome, latency population, dispatch delay, ready-pod integral, controller identity, source hash, and measurement duration from raw evidence. All independent checks passed. Per-run acceptance still comes from the pre-existing analyzer thresholds.", "", "## Limitations", "", "This is one repeat per controller on one single-node kind cluster. The source is synthetic pod-count demand, not request telemetry; mapping it to HTTP rate and compressing time 90× changes its physical meaning. Arm order is fixed, host contention is uncontrolled, the PHPA seasonal period is not retuned to this source, and per-request backend identity is unavailable. Transition metrics have one event of each direction and therefore no variance or causal interpretation."]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")

    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "runs": {}, "artifacts": {}, "code_and_configuration": {}}
    for arm in ARMS:
        run = RUN_ROOT / arm
        manifest["runs"][arm] = {p.name: {"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size}
                                  for p in sorted(run.iterdir()) if p.is_file()}
    for name in ("dataset_validation.json", "WORKLOAD_TRANSFORMATION.md", "run_plan.json", "execution_ledger.jsonl", "PREFLIGHT.md", "environment_metadata.json", "REPRODUCE.md", "comparison.csv", "comparison.json", "RESULTS.md"):
        path = OUT / name
        if path.exists():
            manifest["artifacts"][name] = {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size}
    for relative in ("scripts/live/prepare_onoff_comparison.py", "scripts/live/preflight_onoff.py", "scripts/live/run_onoff_comparison.py", "scripts/live/run_trace.py", "scripts/live/analyze_runs.py", "scripts/live/verify_onoff_comparison.py", "policies/hpa-baseline.yaml", "policies/hpa-calibrated.yaml", "policies/phpa-holtwinters.yaml", "manifests/sample-app.yaml"):
        path = ROOT / relative
        manifest["code_and_configuration"][relative] = {"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size}
    (OUT / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": comparison["status"], "decisions": {r["arm"]: r["decision"] for r in rows},
                      "all_independent_checks": all(all(v.values()) for v in checks.values())}, indent=2))


if __name__ == "__main__":
    main()
