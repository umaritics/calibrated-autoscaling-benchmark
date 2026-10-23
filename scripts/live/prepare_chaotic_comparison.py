#!/usr/bin/env python3
"""Select and freeze the first scientifically eligible D1 chaotic replay."""

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/phpa/phpa-datasets"
OUT = ROOT / "results/live_trace_phase/chaotic_first_comparison"
TRACE = ROOT / "data/live_traces/chaotic_d1_s1.csv"
ROWS = 42
BIN_SECONDS = 10
WARMUP_SECONDS = 120
WARMUP_RPS = 4
MIN_RPS = 20.0
MAX_RPS = 120.0


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenario(path):
    match = re.match(r"chaotic_(\d+)_.*_test\.csv$", path.name)
    return int(match.group(1)) if match else None


def characteristics(values):
    values = np.asarray(values, dtype=float)
    amplitude = float(np.ptp(values))
    differences = np.diff(values)
    material = differences[np.abs(differences) >= max(1.0, .05 * amplitude)]
    reversals = int(np.sum(material[1:] * material[:-1] < 0)) if len(material) > 1 else 0
    major = np.where(np.abs(differences) >= .20 * amplitude)[0] + 1
    gaps = np.diff(major)
    thirds = [values[index:index + 14] for index in (0, 14, 28)]
    major_thirds = sorted({min(2, int(index // 14)) for index in major})
    autocorrelation = float(np.corrcoef(values[:-1], values[1:])[0, 1])
    trend_r2 = float(np.corrcoef(np.arange(len(values)), values)[0, 1] ** 2)
    return {
        "mean": float(values.mean()), "standard_deviation": float(values.std(ddof=1)),
        "coefficient_of_variation": float(values.std(ddof=1) / values.mean()),
        "minimum": float(values.min()), "maximum": float(values.max()),
        "amplitude": amplitude, "peak_to_mean_ratio": float(values.max() / values.mean()),
        "material_direction_changes": reversals, "major_change_count": int(len(major)),
        "major_change_indices_within_window": [int(x) for x in major],
        "major_change_median_gap_observations": float(np.median(gaps)) if len(gaps) else None,
        "major_change_thirds": major_thirds,
        "third_amplitudes": [float(np.ptp(part)) for part in thirds],
        "lag1_autocorrelation": autocorrelation, "linear_trend_r_squared": trend_r2,
    }


def eligible(item):
    return (
        item["coefficient_of_variation"] >= .20
        and item["peak_to_mean_ratio"] >= 1.45
        and item["amplitude"] >= 30
        and item["material_direction_changes"] >= 8
        and item["major_change_count"] >= 6
        and len(item["major_change_thirds"]) >= 2
        and min(item["third_amplitudes"]) >= .25 * item["amplitude"]
        and abs(item["lag1_autocorrelation"]) <= .85
        and item["linear_trend_r_squared"] <= .50
        and item["major_change_median_gap_observations"] <= 8
    )


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


def main():
    candidates = sorted((path for path in DATA.glob("chaotic_*_test.csv") if scenario(path) is not None),
                        key=lambda path: (scenario(path), path.name))
    chosen = None
    for path in candidates:
        frame = pd.read_csv(path, parse_dates=["timestamp"])
        if list(frame.columns) != ["timestamp", "pod_count"] or len(frame) != 672:
            raise RuntimeError(f"unexpected source schema or length: {path}")
        if not (frame.timestamp.diff().dropna().dt.total_seconds() == 900).all():
            raise RuntimeError(f"non-15-minute cadence: {path}")
        for start in range(len(frame) - ROWS + 1):
            stats = characteristics(frame.pod_count.iloc[start:start + ROWS])
            if eligible(stats):
                chosen = path, frame, start, stats
                break
        if chosen:
            break
    if chosen is None:
        raise RuntimeError("no eligible chaotic window")

    source, frame, start, stats = chosen
    stop = start + ROWS
    selected = frame.iloc[start:stop].copy()
    low, high = stats["minimum"], stats["maximum"]
    selected["target_rps"] = MIN_RPS + (MAX_RPS - MIN_RPS) * (
        selected.pod_count.astype(float) - low) / (high - low)
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["replay_second", "source_time", "source_value", "target_rps"])
        for replay_index, (_, row) in enumerate(selected.iterrows()):
            writer.writerow([replay_index * BIN_SECONDS, row.timestamp,
                             int(row.pod_count), float(row.target_rps)])

    replay = pd.read_csv(TRACE)
    frozen_schedule = schedule(replay)
    threshold_high = 90.0
    threshold_low = 40.0
    high_bins = [int(i) for i, value in enumerate(replay.target_rps) if value >= threshold_high]
    low_bins = [int(i) for i, value in enumerate(replay.target_rps) if value <= threshold_low]
    validation = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "decision": "PASS",
        "experiment_label": "accelerated D1 synthetic chaotic pod-demand-proxy replay on a benchmark Kubernetes service",
        "source": {"path": str(source.relative_to(ROOT)), "sha256": sha256(source),
                   "scenario_id": scenario(source), "rows": len(frame), "columns": list(frame.columns),
                   "sampling_interval_seconds": 900, "start": str(frame.timestamp.iloc[0]),
                   "end": str(frame.timestamp.iloc[-1]),
                   "value_range": [int(frame.pod_count.min()), int(frame.pod_count.max())],
                   "units": {"timestamp": "UTC-like naive datetime at 15-minute intervals",
                             "pod_count": "synthetic pod-count demand proxy, not observed HTTP arrivals"}},
        "selection_rule": (
            "Order D1 chaotic test files by numeric scenario ID, then scan every 42-observation window from "
            "earliest to latest. Select the first window with CV >= 0.20, peak/mean >= 1.45, amplitude >= 30 "
            "pod-count units, >=8 direction reversals after ignoring changes below max(1,5% amplitude), >=6 "
            "major adjacent changes of at least 20% amplitude, major changes in >=2 window thirds, amplitude in "
            "each 14-row third >=25% of total amplitude, |lag-1 autocorrelation| <=0.85, linear-time R^2 <=0.50, "
            "and median spacing between major changes <=8 observations. This selects the earliest materially "
            "irregular, non-smooth window without using controller outcomes."),
        "eligibility_thresholds": {"coefficient_of_variation_min": .20, "peak_to_mean_min": 1.45,
             "amplitude_min": 30, "material_direction_changes_min": 8, "major_changes_min": 6,
             "major_change_fraction_of_amplitude": .20, "major_change_thirds_min": 2,
             "each_third_amplitude_fraction_min": .25, "absolute_lag1_autocorrelation_max": .85,
             "linear_trend_r_squared_max": .50, "major_change_median_gap_observations_max": 8},
        "selected_window": {"observation_indices_inclusive": [start, stop - 1], "rows": ROWS,
             "source_start": str(selected.timestamp.iloc[0]), "source_end": str(selected.timestamp.iloc[-1]),
             "source_end_exclusive": str(selected.timestamp.iloc[-1] + pd.Timedelta(minutes=15)),
             "source_duration_seconds": ROWS * 900, "value_range": [int(low), int(high)],
             "characteristics": stats, "replay_trace_path": str(TRACE.relative_to(ROOT)),
             "replay_trace_sha256": sha256(TRACE)},
        "transformation": {"time": "Each observed 900-second source interval becomes one constant 10-second replay bin (90x acceleration).",
             "amplitude": f"target_rps = 20 + 100 * (pod_count - {low:g}) / ({high:g} - {low:g})",
             "minimum_rps": MIN_RPS, "maximum_rps": MAX_RPS, "interpolation": "none",
             "mapping_interpretation": "controller-independent experimental demand proxy, not observed HTTP traffic",
             "warmup_seconds": WARMUP_SECONDS, "warmup_rps": WARMUP_RPS,
             "measurement_seconds": ROWS * BIN_SECONDS, "request_timeout_seconds": 5,
             "maximum_in_flight": 2048,
             "scheduled_measurement_requests": len(frozen_schedule) - WARMUP_SECONDS * WARMUP_RPS},
        "time_scale_assessment": {"source_interval_seconds": 900, "replay_bin_seconds": 10,
             "acceleration_factor": 90, "metrics_server_resolution_seconds": 15,
             "phpa_sync_seconds": 10, "nominal_hpa_reconciliation_seconds": 15,
             "interpretation": "Individual 10-second changes are at or below controller/metrics cadence; the run measures aggregate QoS/capacity under unresolved irregular forcing and cannot support precise per-change reaction-time or prediction claims."},
        "chaotic_metrics_frozen": {
             "spike_bin_rule": f"target_rps >= {threshold_high:g}", "spike_bin_indices": high_bins,
             "low_demand_bin_rule": f"target_rps <= {threshold_low:g}", "low_demand_bin_indices": low_bins,
             "scale_event_rule": "each observed change in desired replicas; direction from signed change",
             "oscillation_rule": "a reversal when consecutive desired-replica changes have opposite signs and occur within 60 seconds",
             "possible_thrashing_rule": "at least three such reversals inside any 120-second interval",
             "excess_low_capacity_rule": "ready-pod-seconds above one replica during frozen low-demand bins",
             "tracking_rule": "descriptive Pearson correlation of target RPS with ready replicas at lags 0,15,30,45,60 seconds; no causal/predictive interpretation",
             "undersupply_proxies": "scheduled-request failures in spike bins plus readiness-deficit telemetry samples",
             "retention_rule": "ready-pod-seconds above one replica in the 60 seconds after each high-to-low major change, reported descriptively"},
        "expected_schedule_sha256": schedule_hash(frozen_schedule),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dataset_validation.json").write_text(json.dumps(validation, indent=2) + "\n")

    arms = ("strawman_hpa", "holtwinters", "calibrated_hpa")
    policies = {"strawman_hpa": "hpa-baseline.yaml", "calibrated_hpa": "hpa-calibrated.yaml",
                "holtwinters": "phpa-holtwinters.yaml"}
    runs = [{"sequence": index + 1, "dataset": "chaotic_d1_s1", "arm": arm, "repeat": 1,
             "warmup": WARMUP_SECONDS, "duration": ROWS * BIN_SECONDS,
             "category": "chaotic_first_comparison"} for index, arm in enumerate(arms)]
    plan = {
        "frozen_utc": datetime.now(timezone.utc).isoformat(), "source_path": str(source.relative_to(ROOT)),
        "source_sha256": sha256(source), "selected_indices_inclusive": [start, stop - 1],
        "replay_path": str(TRACE.relative_to(ROOT)), "replay_sha256": sha256(TRACE),
        "expected_schedule_sha256": validation["expected_schedule_sha256"],
        "mapping": validation["transformation"], "time_scale_assessment": validation["time_scale_assessment"],
        "chaotic_metrics_frozen": validation["chaotic_metrics_frozen"],
        "application": {"image": "php:8.2-apache", "cpu_request": "200m", "cpu_limit": "500m",
             "memory_request": "64Mi", "memory_limit": "128Mi", "replica_bounds": [1, 20],
             "manifest": "manifests/sample-app.yaml", "manifest_sha256": sha256(ROOT / "manifests/sample-app.yaml")},
        "controllers": {"strawman_hpa": {"cpu_target_percent": 50, "scale_down_stabilization_seconds": 60},
             "calibrated_hpa": {"cpu_target_percent": 70, "scale_down_stabilization_seconds": 300,
                                "scale_up_policy": "4 pods per 60 seconds"},
             "holtwinters": {"cpu_target_percent": 50, "sync_period_seconds": 10,
                              "seasonal_periods": 6, "stored_seasons": 4, "alpha": .9, "beta": .2, "gamma": .3}},
        "controller_policy_sha256": {arm: sha256(ROOT / "policies" / filename) for arm, filename in policies.items()},
        "reset": "Delete all HPA/PHPA objects and the app deployment, recreate the unchanged app, restart the PHPA operator only for Holt-Winters, then apply exactly one controller.",
        "acceptance_thresholds": {"complete_schedule": True, "generator_drops": 0,
             "p99_dispatch_delay_below_seconds": .1, "cpu_coverage_at_least": .90,
             "max_metric_gap_below_seconds": 15, "controller_exclusive": True,
             "measurement_window_bracketed": True, "scaling_response_observed": True},
        "run_order_rationale": "User-frozen order: soft HPA, Holt-Winters, tuned HPA.", "runs": runs,
    }
    (OUT / "frozen_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (OUT / "run_plan.json").write_text(json.dumps(runs, indent=2) + "\n")
    (OUT / "WORKLOAD_TRANSFORMATION.md").write_text(f"""# Chaotic dataset provenance and frozen replay

Frozen before controller execution. The source is `{source.relative_to(ROOT)}` (SHA-256 `{sha256(source)}`), containing synthetic `pod_count` demand proxies at 15-minute cadence—not observed HTTP arrivals. The deterministic rule in `dataset_validation.json` selects scenario 1, indices {start}–{stop - 1}; observed values range from {int(low)} to {int(high)} with CV {stats['coefficient_of_variation']:.6f}, peak/mean {stats['peak_to_mean_ratio']:.6f}, {stats['material_direction_changes']} material direction reversals, {stats['major_change_count']} major changes, lag-1 autocorrelation {stats['lag1_autocorrelation']:.6f}, and linear-time R² {stats['linear_trend_r_squared']:.6f}.

Each observation is held for 10 seconds (90× acceleration) and mapped by `{validation['transformation']['amplitude']}`. The established 120-second warmup and 420-second measurement are retained; no longer run is scientifically needed because this window is intended as aggregate irregular forcing, not a resolvable step-response study. No controller receives future values. Replay SHA-256: `{sha256(TRACE)}`. Canonical schedule SHA-256: `{validation['expected_schedule_sha256']}`. Scheduled measurement requests: {validation['transformation']['scheduled_measurement_requests']}.

Individual changes can occur faster than Kubernetes CPU metrics and HPA reconciliation. Results therefore do not support fine-grained reaction-time or correct-prediction claims.
""")
    (OUT / "REPRODUCE.md").write_text("""# Reproduce the first chaotic comparison

```bash
.venv/bin/python scripts/live/prepare_chaotic_comparison.py
.venv/bin/python scripts/live/preflight_chaotic.py
.venv/bin/python scripts/live/run_chaotic_comparison.py
.venv/bin/python scripts/live/verify_chaotic_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner uses the frozen soft HPA → Holt-Winters → tuned HPA order, skips completed arms, and refuses to overwrite unfinished evidence.
""")
    print(json.dumps({"decision": "PASS", "source": str(source.relative_to(ROOT)),
          "source_sha256": sha256(source), "indices": [start, stop - 1], "characteristics": stats,
          "trace_sha256": sha256(TRACE), "schedule_sha256": validation["expected_schedule_sha256"],
          "measurement_requests": validation["transformation"]["scheduled_measurement_requests"]}, indent=2))


if __name__ == "__main__":
    main()
