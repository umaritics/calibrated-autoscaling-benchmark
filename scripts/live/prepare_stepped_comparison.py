#!/usr/bin/env python3
"""Select, validate, and freeze the D1 stepped-pattern live comparison."""

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/stepped_first_comparison"
DATA = ROOT / "data/phpa/phpa-datasets"
TRACE = ROOT / "data/live_traces/stepped_d1_s62.csv"
BIN_SECONDS = 10
WARMUP_SECONDS = 120
WARMUP_RPS = 4
MIN_RPS = 20.0
MAX_RPS = 120.0
REQUEST_TIMEOUT_SECONDS = 5
MAX_IN_FLIGHT = 2048


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schedule(trace):
    items = [(second + quarter / 4, "warmup")
             for second in range(WARMUP_SECONDS) for quarter in range(WARMUP_RPS)]
    for index, row in trace.iterrows():
        count = round(float(row.target_rps) * BIN_SECONDS)
        items.extend((WARMUP_SECONDS + index * BIN_SECONDS + (item + .5) * BIN_SECONDS / count,
                      "measurement") for item in range(count))
    return items


def schedule_hash(items):
    payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in items).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_name(path):
    pattern = re.compile(
        r"stepped_(\d+)_min_pods(\d+)_max_pods(\d+)_step_count(\d+)_"
        r"step_duration(\d+)_step_type([^_]+)_transition_noise([0-9.]+)_test\.csv$")
    match = pattern.match(path.name)
    return None if not match else {
        "scenario": int(match.group(1)), "minimum": int(match.group(2)),
        "maximum": int(match.group(3)), "step_count": int(match.group(4)),
        "duration_hours": int(match.group(5)), "step_type": match.group(6),
        "transition_noise": float(match.group(7)), "path": path,
    }


def boundary_offset(values, plateau_rows):
    """Find the recurring phase with the strongest median adjacent change."""
    scores = []
    for offset in range(plateau_rows):
        boundaries = range(offset if offset else plateau_rows, len(values), plateau_rows)
        changes = [abs(float(values[index] - values[index - 1])) for index in boundaries]
        scores.append((float(np.median(changes)) if changes else -1, -offset, offset))
    return max(scores)[2]


def main():
    candidates = [item for path in DATA.glob("stepped_*_test.csv")
                  if (item := parse_name(path)) is not None]
    eligible = []
    for item in candidates:
        # Four 15-minute observations per source hour. Require a full replayed
        # plateau to exceed 300 s stabilization plus two nominal HPA cycles.
        plateau_rows = item["duration_hours"] * 4
        if plateau_rows * BIN_SECONDS < 330:
            continue
        frame = pd.read_csv(item["path"], parse_dates=["timestamp"])
        values = pd.to_numeric(frame.pod_count, errors="coerce").to_numpy(dtype=float)
        offset = boundary_offset(values, plateau_rows)
        boundaries = list(range(offset if offset else plateau_rows, len(values), plateau_rows))
        threshold = .20 * (item["maximum"] - item["minimum"])
        for first in range(len(boundaries) - 1):
            left, right = boundaries[first], boundaries[first + 1]
            if left - plateau_rows < 0 or right + plateau_rows > len(values):
                continue
            guard = max(2, plateau_rows // 4)
            medians = [float(np.median(values[a + guard:b])) for a, b in
                       ((left - plateau_rows, left), (left, right), (right, right + plateau_rows))]
            deltas = [medians[1] - medians[0], medians[2] - medians[1]]
            if min(abs(delta) for delta in deltas) >= threshold and deltas[0] * deltas[1] < 0:
                eligible.append((item["duration_hours"], item["scenario"], left - plateau_rows,
                                 item, frame, offset, medians, deltas))
                break
    if not eligible:
        raise RuntimeError("no eligible stepped source interval with opposite material transitions")
    _, scenario, start, item, frame, offset, medians, deltas = min(eligible, key=lambda x: x[:3])
    plateau_rows = item["duration_hours"] * 4
    stop = start + 3 * plateau_rows
    selected = frame.iloc[start:stop].copy()
    low, high = float(selected.pod_count.min()), float(selected.pod_count.max())
    selected["target_rps"] = MIN_RPS + (MAX_RPS - MIN_RPS) * (
        selected.pod_count.astype(float) - low) / (high - low)
    duration = len(selected) * BIN_SECONDS
    transition_indices = [plateau_rows, 2 * plateau_rows]

    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["replay_second", "source_time", "source_value", "target_rps"])
        for replay_index, (_, row) in enumerate(selected.iterrows()):
            writer.writerow([replay_index * BIN_SECONDS, row.timestamp,
                             int(row.pod_count), float(row.target_rps)])

    replay = pd.read_csv(TRACE)
    frozen_schedule = schedule(replay)
    source = item["path"]
    source_hash, trace_hash = sha256(source), sha256(TRACE)
    expected_hash = schedule_hash(frozen_schedule)
    plateau_details = []
    for number in range(3):
        part = selected.iloc[number * plateau_rows:(number + 1) * plateau_rows]
        plateau_details.append({
            "number": number + 1,
            "source_indices_inclusive": [start + number * plateau_rows,
                                          start + (number + 1) * plateau_rows - 1],
            "source_start": str(part.timestamp.iloc[0]), "source_end": str(part.timestamp.iloc[-1]),
            "source_duration_seconds": plateau_rows * 900,
            "replay_window_seconds": [number * plateau_rows * BIN_SECONDS,
                                       (number + 1) * plateau_rows * BIN_SECONDS],
            "replay_duration_seconds": plateau_rows * BIN_SECONDS,
            "core_median_pod_count": medians[number],
            "observed_range": [int(part.pod_count.min()), int(part.pod_count.max())],
        })
    transitions = []
    for number, local in enumerate(transition_indices):
        before = int(selected.pod_count.iloc[local - 1]); after = int(selected.pod_count.iloc[local])
        transitions.append({
            "number": number + 1, "direction": "up" if deltas[number] > 0 else "down",
            "source_boundary_index": start + local,
            "source_timestamp": str(selected.timestamp.iloc[local]),
            "measurement_second": local * BIN_SECONDS,
            "raw_adjacent_change": after - before,
            "core_median_change": deltas[number],
            "mapped_core_median_rps_change": deltas[number] * 100 / (high - low),
            "post_step_window_seconds": [local * BIN_SECONDS, local * BIN_SECONDS + 120],
        })

    validation = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "decision": "PASS",
        "experiment_label": "accelerated D1 synthetic stepped pod-demand-proxy replay on a benchmark Kubernetes service",
        "source": {"path": str(source.relative_to(ROOT)), "sha256": source_hash,
                   "scenario_id": scenario, "rows": len(frame), "columns": list(frame.columns),
                   "sampling_interval_seconds": 900,
                   "start": str(frame.timestamp.iloc[0]), "end": str(frame.timestamp.iloc[-1]),
                   "value_range": [int(frame.pod_count.min()), int(frame.pod_count.max())],
                   "filename_parameters": {k: item[k] for k in
                       ("minimum", "maximum", "step_count", "duration_hours", "step_type", "transition_noise")},
                   "units": {"timestamp": "UTC-like naive datetime at 15-minute intervals",
                             "pod_count": "synthetic pod-count demand proxy"}},
        "selection_rule": (
            "Parse every D1 stepped test filename. A scenario is timing-eligible when one nominal source plateau "
            "(step_duration hours × four 15-minute observations/hour × 10 replay seconds/observation) lasts at "
            "least 330 seconds, covering the unchanged 300-second tuned-HPA stabilization plus two nominal HPA "
            "cycles. Infer the recurring boundary phase that maximizes median absolute adjacent change. Using "
            "core medians after a one-quarter-plateau transition guard, require two adjacent opposite-direction "
            "changes each at least 20% of the configured min-max amplitude. Choose shortest nominal duration, "
            "then lowest scenario ID, then earliest eligible triplet. This controller-independent rule selects "
            "scenario 62 and was frozen before any controller run."),
        "boundary_detection": {"period_observations": plateau_rows, "phase_offset": offset,
                               "transition_guard_observations": max(2, plateau_rows // 4)},
        "selected_window": {"observation_indices_inclusive": [start, stop - 1], "rows": len(selected),
                            "source_start": str(selected.timestamp.iloc[0]),
                            "source_end": str(selected.timestamp.iloc[-1]),
                            "source_end_exclusive": str(selected.timestamp.iloc[-1] + pd.Timedelta(minutes=15)),
                            "source_duration_seconds": len(selected) * 900,
                            "value_range": [int(low), int(high)], "plateaus": plateau_details,
                            "transitions": transitions, "transition_count": len(transitions),
                            "directions": [x["direction"] for x in transitions],
                            "replay_trace_path": str(TRACE.relative_to(ROOT)),
                            "replay_trace_sha256": trace_hash},
        "transformation": {"time": "Each observed 900-second source interval becomes one constant 10-second replay bin (90x acceleration).",
                           "amplitude": f"target_rps = 20 + 100 * (pod_count - {low:g}) / ({high:g} - {low:g})",
                           "minimum_rps": MIN_RPS, "maximum_rps": MAX_RPS,
                           "mapping_interpretation": "controller-independent experimental demand proxy, not observed HTTP traffic",
                           "interpolation": "none; observed values are held constant within each replay bin",
                           "difference_from_growing_onoff": "Same affine 20-120 RPS envelope; stepped uses its frozen selected-window extrema and a longer predeclared measurement to preserve full plateaus.",
                           "warmup_seconds": WARMUP_SECONDS, "warmup_rps": WARMUP_RPS,
                           "measurement_seconds": duration,
                           "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
                           "maximum_in_flight": MAX_IN_FLIGHT,
                           "scheduled_measurement_requests": len(frozen_schedule) - WARMUP_SECONDS * WARMUP_RPS},
        "time_scale_assessment": {"source_interval_seconds": 900, "replay_bin_seconds": BIN_SECONDS,
                                  "acceleration_factor": 90, "metrics_server_resolution_seconds": 15,
                                  "phpa_sync_seconds": 10, "nominal_hpa_reconciliation_seconds": 15,
                                  "plateau_replay_seconds": plateau_rows * BIN_SECONDS,
                                  "interpretation": "Individual noisy 10-second bins are below HPA metric resolution, but each 400-second main plateau spans about 26.7 metric/HPA resolutions, 40 PHPA sync periods, and exceeds tuned-HPA scale-down stabilization by 100 seconds."},
        "transition_analysis": {"post_up_window_seconds": 120, "post_down_window_seconds": 120,
                                "response_baseline": "last telemetry sample strictly before boundary",
                                "response": "first matching desired/ready replica change from the baseline",
                                "pre_step_capacity_sufficient": "zero failures in the first 30 seconds after an upward step",
                                "down_excess_capacity": "integral of max(ready - final-60-second minimum ready, 0) over the lower plateau",
                                "lag_resolution_warning": "lags closer than the 5-second collector cadence are not distinguishable",
                                "proactivity_rule": "only a desired increase before the observed upward boundary counts as temporal pre-scaling; surplus replicas alone do not"},
        "expected_schedule_sha256": expected_hash,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dataset_validation.json").write_text(json.dumps(validation, indent=2) + "\n")

    policies = {
        "strawman_hpa": {"kind": "HorizontalPodAutoscaler", "cpu_target_percent": 50, "scale_down_stabilization_seconds": 60},
        "calibrated_hpa": {"kind": "HorizontalPodAutoscaler", "cpu_target_percent": 70, "scale_down_stabilization_seconds": 300, "scale_up_policy": "4 pods per 60 seconds"},
        "holtwinters": {"kind": "PredictiveHorizontalPodAutoscaler", "cpu_target_percent": 50,
                         "sync_period_seconds": 10, "seasonal_periods": 6, "stored_seasons": 4,
                         "alpha": .9, "beta": .2, "gamma": .3},
    }
    arms = ("calibrated_hpa", "holtwinters", "strawman_hpa")
    plan = {
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source.relative_to(ROOT)), "source_sha256": source_hash,
        "selected_indices_inclusive": [start, stop - 1],
        "replay_path": str(TRACE.relative_to(ROOT)), "replay_sha256": trace_hash,
        "expected_schedule_sha256": expected_hash, "transitions": transitions,
        "mapping": validation["transformation"], "transition_analysis": validation["transition_analysis"],
        "application": {"image": "php:8.2-apache", "cpu_request": "200m", "cpu_limit": "500m",
                        "memory_request": "64Mi", "memory_limit": "128Mi", "replica_bounds": [1, 20],
                        "manifest": "manifests/sample-app.yaml", "manifest_sha256": sha256(ROOT / "manifests/sample-app.yaml")},
        "controllers": policies,
        "controller_policy_sha256": {arm: sha256(ROOT / "policies" / name) for arm, name in
                                     {"strawman_hpa": "hpa-baseline.yaml", "calibrated_hpa": "hpa-calibrated.yaml", "holtwinters": "phpa-holtwinters.yaml"}.items()},
        "reset": "Delete all HPA/PHPA objects and the app deployment, recreate the unchanged app, restart the PHPA operator only for Holt-Winters, then apply exactly one controller.",
        "acceptance_thresholds": {"complete_schedule": True, "generator_drops": 0,
                                  "p99_dispatch_delay_below_seconds": .1, "cpu_coverage_at_least": .90,
                                  "max_metric_gap_below_seconds": 15, "controller_exclusive": True,
                                  "measurement_window_bracketed": True, "scaling_response_observed": True},
        "runs": [{"sequence": index + 1, "dataset": "stepped_d1_s62", "arm": arm, "repeat": 1,
                  "warmup": WARMUP_SECONDS, "duration": duration, "category": "stepped_first_comparison"}
                 for index, arm in enumerate(arms)],
    }
    (OUT / "frozen_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (OUT / "run_plan.json").write_text(json.dumps(plan["runs"], indent=2) + "\n")
    (OUT / "WORKLOAD_TRANSFORMATION.md").write_text(
        f"""# Stepped dataset provenance and frozen replay

Frozen before controller execution. The source is `{source.relative_to(ROOT)}` (SHA-256 `{source_hash}`), with 672 synthetic `pod_count` observations at 15-minute cadence. These are demand proxies, not observed HTTP requests.

The deterministic selection rule in `dataset_validation.json` selected scenario 62, indices {start}–{stop - 1}, containing three complete 10-source-hour plateaus and two opposite material transitions. At 90× acceleration, each observation is held for 10 seconds and each plateau lasts 400 seconds. The 1,200-second measurement is longer than prior 420-second comparisons specifically so the unchanged 300-second tuned-HPA stabilization can be observed; timing was frozen for every arm before execution.

The mapping is `{validation['transformation']['amplitude']}` over the same 20–120 RPS envelope used by growing/on-off. No interpolation or future observation is supplied to any controller. Replay SHA-256: `{trace_hash}`. Canonical request-schedule SHA-256: `{expected_hash}`. Scheduled measurement requests: {validation['transformation']['scheduled_measurement_requests']}.
""")
    (OUT / "REPRODUCE.md").write_text("""# Reproduce the first stepped comparison

```bash
.venv/bin/python scripts/live/prepare_stepped_comparison.py
.venv/bin/python scripts/live/preflight_stepped.py
.venv/bin/python scripts/live/run_stepped_comparison.py
.venv/bin/python scripts/live/verify_stepped_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner uses the frozen tuned → Holt-Winters → soft order, skips complete arms, and refuses to overwrite unfinished evidence.
""")
    print(json.dumps({"decision": "PASS", "source": str(source.relative_to(ROOT)),
                      "source_sha256": source_hash, "indices": [start, stop - 1],
                      "transitions": transitions, "trace_sha256": trace_hash,
                      "schedule_sha256": expected_hash,
                      "measurement_requests": validation["transformation"]["scheduled_measurement_requests"]}, indent=2))


if __name__ == "__main__":
    main()
