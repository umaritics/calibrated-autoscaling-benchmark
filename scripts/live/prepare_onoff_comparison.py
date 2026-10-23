#!/usr/bin/env python3
"""Validate and freeze the dataset-derived on/off live comparison inputs."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/onoff_first_comparison"
ONLINE = ROOT / "data/workloads-predictional-scaling-patterns/kaggle/kaggle/data/patterns/onoff"
SOURCE = ROOT / "data/phpa/phpa-datasets/onoff_81_min_pods20_max_pods60_on_duration4_off_duration4_transition_typesharp_transition_noise0.3_test.csv"
TRACE = ROOT / "data/live_traces/onoff_d1_s81.csv"
SOURCE_ROWS = 42
PEAK_RPS = 120.0


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    online_files = sorted(ONLINE.glob("*.csv"))
    online_columns = {}
    for path in online_files:
        frame = pd.read_csv(path)
        online_columns[path.name] = list(frame.columns)
    demand_columns = {"requests", "request_count", "rps", "target_rps", "incoming_requests"}
    online_has_demand = any(demand_columns.intersection(columns) for columns in online_columns.values())
    if online_has_demand:
        raise RuntimeError("online release unexpectedly contains a demand column; review selection")

    frame = pd.read_csv(SOURCE, parse_dates=["timestamp"])
    if list(frame.columns) != ["timestamp", "pod_count"] or len(frame) != 672:
        raise RuntimeError("unexpected D1 source schema or row count")
    spacing = frame.timestamp.diff().dropna().dt.total_seconds()
    if not (spacing == 900).all() or frame.pod_count.isna().any() or (frame.pod_count < 0).any():
        raise RuntimeError("invalid source timestamps or pod_count values")
    selected = frame.iloc[:SOURCE_ROWS].copy()
    maximum = float(selected.pod_count.max())
    selected["target_rps"] = PEAK_RPS * selected.pod_count.astype(float) / maximum
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["replay_second", "source_time", "source_value", "target_rps"])
        for index, row in selected.iterrows():
            writer.writerow([index * 10, row.timestamp, int(row.pod_count), row.target_rps])

    segments = [
        {"state": "high", "start_index": 0, "end_index_exclusive": 16},
        {"state": "low", "start_index": 16, "end_index_exclusive": 32},
        {"state": "high", "start_index": 32, "end_index_exclusive": 42},
    ]
    for segment in segments:
        values = selected.pod_count.iloc[segment["start_index"]:segment["end_index_exclusive"]]
        segment.update(count=len(values), minimum=int(values.min()), maximum=int(values.max()),
                       median=float(values.median()), unique_values=sorted(int(x) for x in values.unique()))
    transitions = [
        {"source_index": 16, "source_timestamp": str(selected.timestamp.iloc[16]),
         "measurement_second": 160, "from": "high", "to": "low"},
        {"source_index": 32, "source_timestamp": str(selected.timestamp.iloc[32]),
         "measurement_second": 320, "from": "low", "to": "high"},
    ]
    scheduled_measurement = sum(round(float(value) * 10) for value in selected.target_rps)
    validation = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS",
        "experiment_label": "D1 synthetic on/off pod-demand-proxy replay on a benchmark Kubernetes service",
        "online_release_assessment": {
            "path": str(ONLINE.relative_to(ROOT)), "files": len(online_files),
            "contains_incoming_demand": False, "columns_by_file": online_columns,
            "reason": "The files are observed controller/replica/CPU outputs, not incoming workload observations.",
        },
        "source": {"path": str(SOURCE.relative_to(ROOT)), "sha256": sha256(SOURCE),
                   "rows": len(frame), "columns": list(frame.columns), "units": {"timestamp": "UTC-like naive datetime at 15-minute intervals", "pod_count": "synthetic pod-count demand proxy"},
                   "duration_seconds": int((frame.timestamp.iloc[-1] - frame.timestamp.iloc[0]).total_seconds() + 900)},
        "selection_rule": "Use test split; select scenario 81 because it is the lowest numeric ID in the shortest balanced (4 h on / 4 h off), sharp-transition subgroup; use its first 42 chronological observations. This rule was fixed before controller outcomes.",
        "selected_window": {"rows": SOURCE_ROWS, "source_start": str(selected.timestamp.iloc[0]),
                            "source_end_exclusive": str(selected.timestamp.iloc[-1] + pd.Timedelta(minutes=15)),
                            "source_duration_seconds": SOURCE_ROWS * 900, "segments": segments,
                            "transitions": transitions, "source_maximum": maximum,
                            "replay_trace_path": str(TRACE.relative_to(ROOT)), "replay_trace_sha256": sha256(TRACE),
                            "scheduled_measurement_requests": scheduled_measurement},
        "transformation": {"time": "Each 900-second source interval becomes one 10-second replay interval (constant 90x compression).",
                           "amplitude": "target_rps = 120 * pod_count / max(pod_count in the frozen 42-row window)",
                           "peak_rps": PEAK_RPS, "warmup_seconds": 120, "warmup_rps": 4,
                           "measurement_seconds": 420, "request_timeout_seconds": 5,
                           "maximum_in_flight": 2048},
    }
    (OUT / "dataset_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    plan = [{"sequence": i + 1, "dataset": "onoff_d1_s81", "arm": arm, "repeat": 1,
             "warmup": 120, "duration": 420, "category": "onoff_first_comparison"}
            for i, arm in enumerate(("strawman_hpa", "calibrated_hpa", "holtwinters"))]
    (OUT / "run_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    provenance = f"""# On/off dataset provenance and frozen replay

Frozen before any controller execution.

The preferred D2 online release under `{ONLINE.relative_to(ROOT)}` was inspected first. Its seven CSVs contain controller decisions, replica state, CPU telemetry, and cumulative scaling history. They contain no request-count or request-rate field and therefore are not replayed as incoming demand.

The replay source is `{SOURCE.relative_to(ROOT)}` (SHA-256 `{sha256(SOURCE)}`). It has 672 genuine released synthetic observations with columns `timestamp` and `pod_count`, sampled every 15 minutes. `pod_count` is a simulated pod-count demand proxy—not observed HTTP demand, utilization, or measured replicas from a live service. The complete test split spans 168 hours.

Scenario 81 is the lowest numeric identifier in the shortest balanced, sharp-transition subgroup (`on_duration4`, `off_duration4`). The frozen window is the first 42 chronological test observations. Its three visible segments are high (indices 0–15, median {segments[0]['median']:.1f}), low (16–31, all 20), and high (32–41, median {segments[2]['median']:.1f}); boundaries are source indices 16 and 32. Thus the measurement includes one high→low and one low→high transition without outcome-based window selection.

Each 15-minute interval is replayed for 10 seconds, a constant 90× compression, so this is explicitly a **derived workload**. Request rate is `120 × pod_count / 78`, where 78 is the frozen window maximum and 120 requests/s is the existing live protocol peak. No smoothing, imputation, rearrangement, or per-controller adjustment occurs. The measurement schedule has {scheduled_measurement} requests over 420 seconds, preceded by the established 120-second, 4 requests/s warmup. All arms use the same trace hash `{sha256(TRACE)}`.

Neither HPA sees future demand. The PHPA sees Kubernetes CPU history only. Compression changes the physical time scale and the source variable is a pod-demand proxy mapped to benchmark HTTP traffic, so results do not reproduce the authors' online experiment or represent production service latency.
"""
    (OUT / "WORKLOAD_TRANSFORMATION.md").write_text(provenance)
    reproduce = """# Reproduce the first on/off comparison

Use the existing `calibrated-live` kind cluster and repository virtual environment:

```bash
.venv/bin/python scripts/live/prepare_onoff_comparison.py
.venv/bin/python scripts/live/preflight_onoff.py
.venv/bin/python scripts/live/run_onoff_comparison.py
.venv/bin/python scripts/live/verify_onoff_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

The runner refuses to overwrite unfinished or completed evidence. Delete nothing to resume: completed arms are skipped and an unfinished arm requires manual review. Raw request and Kubernetes telemetry are retained per arm.
"""
    (OUT / "REPRODUCE.md").write_text(reproduce)
    print(json.dumps({"decision": "PASS", "source_sha256": sha256(SOURCE),
                      "trace_sha256": sha256(TRACE), "measurement_requests": scheduled_measurement,
                      "transitions": transitions}, indent=2))


if __name__ == "__main__":
    main()
