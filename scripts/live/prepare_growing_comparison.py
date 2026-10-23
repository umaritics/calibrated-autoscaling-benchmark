#!/usr/bin/env python3
"""Select, validate, and freeze the D1 growing-pattern live comparison."""

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/growing_first_comparison"
DATA = ROOT / "data/phpa/phpa-datasets"
TRACE = ROOT / "data/live_traces/growing_d1_s1.csv"
WINDOW_ROWS = 42
BIN_SECONDS = 10
MIN_RPS = 20.0
MAX_RPS = 120.0
WARMUP_SECONDS = 120
WARMUP_RPS = 4
MEASUREMENT_SECONDS = WINDOW_ROWS * BIN_SECONDS
REQUEST_TIMEOUT_SECONDS = 5
MAX_IN_FLIGHT = 2048


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schedule(trace):
    result = [(second + quarter / 4, "warmup")
              for second in range(WARMUP_SECONDS) for quarter in range(WARMUP_RPS)]
    for index, row in trace.iterrows():
        count = round(float(row.target_rps) * BIN_SECONDS)
        result.extend((WARMUP_SECONDS + index * BIN_SECONDS + (item + .5) * BIN_SECONDS / count,
                       "measurement") for item in range(count))
    return result


def schedule_hash(items):
    payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in items).encode()
    return hashlib.sha256(payload).hexdigest()


def main():
    candidates = []
    pattern = re.compile(r"growing_(\d+)_.*cyclic_growth(False)_.*_test\.csv$")
    for path in DATA.glob("growing_*_test.csv"):
        match = pattern.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise RuntimeError("no non-cyclic D1 growing test scenarios found")
    scenario_id, source = min(candidates)
    frame = pd.read_csv(source, parse_dates=["timestamp"])
    if list(frame.columns) != ["timestamp", "pod_count"] or len(frame) != 672:
        raise RuntimeError("unexpected D1 source schema or row count")
    spacing = frame.timestamp.diff().dropna().dt.total_seconds()
    values = pd.to_numeric(frame.pod_count, errors="coerce")
    if not (spacing == 900).all() or values.isna().any() or (values < 0).any():
        raise RuntimeError("invalid source timestamps or pod_count values")

    slopes = []
    x = np.arange(WINDOW_ROWS, dtype=float)
    for start in range(len(frame) - WINDOW_ROWS + 1):
        window = values.iloc[start:start + WINDOW_ROWS].to_numpy(dtype=float)
        slopes.append(float(np.polyfit(x, window, 1)[0]))
    start = int(np.argmax(slopes))
    stop = start + WINDOW_ROWS
    selected = frame.iloc[start:stop].copy()
    low = float(selected.pod_count.min())
    high = float(selected.pod_count.max())
    if high <= low or slopes[start] <= 0:
        raise RuntimeError("selected growing window lacks positive variation")
    selected["target_rps"] = MIN_RPS + (MAX_RPS - MIN_RPS) * (
        selected.pod_count.astype(float) - low) / (high - low)

    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["replay_second", "source_time", "source_value", "target_rps"])
        for replay_index, (_, row) in enumerate(selected.iterrows()):
            writer.writerow([replay_index * BIN_SECONDS, row.timestamp,
                             int(row.pod_count), float(row.target_rps)])

    generated_trace = pd.read_csv(TRACE)
    frozen_schedule = schedule(generated_trace)
    threshold_rps = 70.0
    sustained_bins = 3
    onset_index = next(index for index in range(len(selected) - sustained_bins + 1)
                       if (selected.target_rps.iloc[index:index + sustained_bins] >= threshold_rps).all())
    early = selected.iloc[:14]
    late = selected.iloc[-14:]
    source_hash = sha256(source)
    trace_hash = sha256(TRACE)
    expected_schedule_hash = schedule_hash(frozen_schedule)

    validation = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS",
        "experiment_label": "accelerated D1 synthetic growing pod-demand-proxy replay on a benchmark Kubernetes service",
        "source": {
            "path": str(source.relative_to(ROOT)), "sha256": source_hash,
            "scenario_id": scenario_id, "rows": len(frame), "columns": list(frame.columns),
            "sampling_interval_seconds": 900,
            "start": str(frame.timestamp.iloc[0]), "end": str(frame.timestamp.iloc[-1]),
            "value_range": [int(values.min()), int(values.max())],
            "units": {"timestamp": "UTC-like naive datetime at 15-minute intervals",
                      "pod_count": "synthetic pod-count demand proxy"},
        },
        "selection_rule": (
            "Use the test split and the lowest numeric non-cyclic growing scenario ID. Within that scenario, "
            "select the earliest 42-observation contiguous window attaining the maximum positive ordinary "
            "least-squares pod_count slope. Ties resolve to the earliest start. The rule and result were frozen "
            "before any controller outcome was observed."),
        "selected_window": {
            "observation_indices_inclusive": [start, stop - 1], "rows": WINDOW_ROWS,
            "source_start": str(selected.timestamp.iloc[0]), "source_end": str(selected.timestamp.iloc[-1]),
            "source_end_exclusive": str(selected.timestamp.iloc[-1] + pd.Timedelta(minutes=15)),
            "source_duration_seconds": WINDOW_ROWS * 900,
            "value_range": [int(low), int(high)], "first_value": int(selected.pod_count.iloc[0]),
            "last_value": int(selected.pod_count.iloc[-1]), "ols_slope_pods_per_observation": slopes[start],
            "ols_slope_pods_per_source_hour": slopes[start] * 4,
            "early_third_mean": float(early.pod_count.mean()),
            "late_third_mean": float(late.pod_count.mean()),
            "late_minus_early_mean": float(late.pod_count.mean() - early.pod_count.mean()),
            "decreasing_steps": int((selected.pod_count.diff() < 0).sum()),
            "replay_trace_path": str(TRACE.relative_to(ROOT)), "replay_trace_sha256": trace_hash,
        },
        "transformation": {
            "time": "Each observed 900-second source interval becomes one constant 10-second replay bin (90x acceleration).",
            "amplitude": "target_rps = 20 + 100 * (pod_count - 90) / (99 - 90)",
            "minimum_rps": MIN_RPS, "maximum_rps": MAX_RPS,
            "mapping_interpretation": "controller-independent experimental demand proxy, not reconstructed HTTP traffic",
            "interpolation": "none; observed values are held constant within each replay bin",
            "warmup_seconds": WARMUP_SECONDS, "warmup_rps": WARMUP_RPS,
            "measurement_seconds": MEASUREMENT_SECONDS,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS, "maximum_in_flight": MAX_IN_FLIGHT,
            "scheduled_measurement_requests": len(frozen_schedule) - WARMUP_SECONDS * WARMUP_RPS,
        },
        "time_scale_assessment": {
            "source_interval_seconds": 900, "replay_bin_seconds": BIN_SECONDS, "acceleration_factor": 90,
            "metrics_server_resolution_seconds": 15, "phpa_sync_seconds": 10,
            "nominal_hpa_reconciliation_seconds": 15,
            "measurement_metric_resolutions": MEASUREMENT_SECONDS / 15,
            "measurement_phpa_sync_periods": MEASUREMENT_SECONDS / 10,
            "interpretation": (
                "Individual 10-second source bins are not reliably separable by 15-second CPU metrics/HPA cycles. "
                "The 420-second window nevertheless contains 28 metric resolutions and 42 PHPA sync periods, so "
                "only response to the sustained overall rise is interpreted. Native 10.5-hour timing is not claimed."),
        },
        "growth_response_definition": {
            "sustained_growth_threshold_rps": threshold_rps, "consecutive_bins": sustained_bins,
            "onset_measurement_second": onset_index * BIN_SECONDS,
            "response_baseline_window_seconds": [max(0, onset_index * BIN_SECONDS - 30), onset_index * BIN_SECONDS],
            "response": "first observed desired/ready replica count above the last pre-onset telemetry value",
            "early_window_seconds": [0, 140], "late_window_seconds": [280, 420],
            "failure_concentration_window_seconds": [onset_index * BIN_SECONDS, 420],
            "proactivity_rule": (
                "A pre-onset scale-up is reported descriptively only if it follows the start of the rising replay; "
                "replica count alone is not evidence of causal prediction."),
        },
        "expected_schedule_sha256": expected_schedule_hash,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dataset_validation.json").write_text(json.dumps(validation, indent=2) + "\n")

    policy_details = {
        "strawman_hpa": {"kind": "HorizontalPodAutoscaler", "cpu_target_percent": 50,
                          "scale_down_stabilization_seconds": 60},
        "calibrated_hpa": {"kind": "HorizontalPodAutoscaler", "cpu_target_percent": 70,
                            "scale_down_stabilization_seconds": 300,
                            "scale_up_policy": "4 pods per 60 seconds"},
        "holtwinters": {"kind": "PredictiveHorizontalPodAutoscaler", "cpu_target_percent": 50,
                         "sync_period_seconds": 10, "seasonal_periods": 6, "stored_seasons": 4,
                         "alpha": 0.9, "beta": 0.2, "gamma": 0.3},
    }
    arms = ("strawman_hpa", "calibrated_hpa", "holtwinters")
    plan = {
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source.relative_to(ROOT)), "source_sha256": source_hash,
        "selected_indices_inclusive": [start, stop - 1],
        "replay_path": str(TRACE.relative_to(ROOT)), "replay_sha256": trace_hash,
        "expected_schedule_sha256": expected_schedule_hash,
        "mapping": validation["transformation"], "growth_response_definition": validation["growth_response_definition"],
        "application": {"image": "php:8.2-apache", "cpu_request": "200m", "cpu_limit": "500m",
                        "memory_request": "64Mi", "memory_limit": "128Mi",
                        "replica_bounds": [1, 20], "manifest": "manifests/sample-app.yaml",
                        "manifest_sha256": sha256(ROOT / "manifests/sample-app.yaml")},
        "controllers": policy_details,
        "acceptance_thresholds": {"complete_schedule": True, "generator_drops": 0,
                                  "p99_dispatch_delay_below_seconds": 0.1,
                                  "cpu_coverage_at_least": 0.90, "max_metric_gap_below_seconds": 15,
                                  "controller_exclusive": True, "measurement_window_bracketed": True,
                                  "scaling_response_observed": True},
        "runs": [{"sequence": index + 1, "dataset": "growing_d1_s1", "arm": arm,
                  "repeat": 1, "warmup": WARMUP_SECONDS, "duration": MEASUREMENT_SECONDS,
                  "category": "growing_first_comparison"} for index, arm in enumerate(arms)],
    }
    (OUT / "frozen_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (OUT / "run_plan.json").write_text(json.dumps(plan["runs"], indent=2) + "\n")
    provenance = f"""# Growing dataset provenance and frozen replay

Frozen before controller execution.

The source is `{source.relative_to(ROOT)}` (SHA-256 `{source_hash}`). It contains 672 released synthetic `pod_count` observations at a complete 15-minute cadence. The values are a generated pod-demand proxy, not observed HTTP requests or measured live replicas.

The deterministic selection first chooses scenario 1 because it is the lowest numeric non-cyclic growing test scenario. It then evaluates every contiguous 42-observation window in that one scenario and selects the earliest window with the maximum ordinary least-squares slope: source indices {start}–{stop - 1}, `{selected.timestamp.iloc[0]}` through `{selected.timestamp.iloc[-1]}`. Values range from {int(low)} to {int(high)}, the fitted slope is {slopes[start]:.9f} pods per observation ({slopes[start] * 4:.9f} per source hour), and the late-third mean exceeds the early-third mean by {late.pod_count.mean() - early.pod_count.mean():.6f}. This outcome-independent rule intentionally identifies a sustained-growth episode without using controller results.

Each observed 15-minute interval is held for 10 replay seconds, a constant 90× acceleration. No intermediate source observations are invented. The affine proxy `target_rps = 20 + 100 × (pod_count − 90) / 9` spans the previously validated 20–120 requests/s benchmark envelope and is identical for all controllers. It is not a reconstruction of original traffic. The 420-second measurement provides 28 nominal Metrics Server/HPA resolutions and 42 PHPA sync periods; interpretation is limited to the sustained ramp, not individual 10-second steps or native-time behavior.

The scheduled measurement contains {validation['transformation']['scheduled_measurement_requests']} requests. The replay SHA-256 is `{trace_hash}` and canonical deterministic schedule SHA-256 is `{expected_schedule_hash}`.
"""
    (OUT / "WORKLOAD_TRANSFORMATION.md").write_text(provenance)
    reproduce = """# Reproduce the first growing comparison

Use the existing `calibrated-live` kind cluster and repository environment:

```bash
.venv/bin/python scripts/live/prepare_growing_comparison.py
.venv/bin/python scripts/live/preflight_growing.py
.venv/bin/python scripts/live/run_growing_comparison.py
.venv/bin/python scripts/live/verify_growing_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner skips completed arms and refuses to overwrite unfinished evidence. Review and preserve any unfinished directory separately before resuming.
"""
    (OUT / "REPRODUCE.md").write_text(reproduce)
    print(json.dumps({"decision": "PASS", "source": str(source.relative_to(ROOT)),
                      "source_sha256": source_hash, "indices": [start, stop - 1],
                      "trace_sha256": trace_hash, "schedule_sha256": expected_schedule_hash,
                      "measurement_requests": validation["transformation"]["scheduled_measurement_requests"],
                      "growth_onset_second": onset_index * BIN_SECONDS}, indent=2))


if __name__ == "__main__":
    main()
