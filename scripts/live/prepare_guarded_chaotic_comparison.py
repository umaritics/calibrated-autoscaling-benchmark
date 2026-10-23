#!/usr/bin/env python3
"""Freeze the lower-intensity resource-guarded D1 chaotic variant."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "results/live_trace_phase/chaotic_first_comparison/frozen_plan.json"
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
TRACE = ROOT / "data/live_traces/chaotic_guarded_d1_s1.csv"
MIN_RPS, MAX_RPS = 10.0, 45.0
WARMUP, DURATION, BIN_SECONDS = 120, 420, 10


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schedule(trace):
    result = [(second + quarter / 4, "warmup") for second in range(WARMUP) for quarter in range(4)]
    for index, row in trace.iterrows():
        count = round(float(row.target_rps) * BIN_SECONDS)
        result.extend((WARMUP + index * BIN_SECONDS + (item + .5) * BIN_SECONDS / count,
                       "measurement") for item in range(count))
    return result


def schedule_hash(items):
    payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in items).encode()
    return hashlib.sha256(payload).hexdigest()


def main():
    prior = json.loads(OLD.read_text())
    source = ROOT / prior["source_path"]
    frame = pd.read_csv(source, parse_dates=["timestamp"])
    start, stop_inclusive = prior["selected_indices_inclusive"]
    selected = frame.iloc[start:stop_inclusive + 1].copy()
    low, high = float(selected.pod_count.min()), float(selected.pod_count.max())
    selected["target_rps"] = MIN_RPS + (MAX_RPS - MIN_RPS) * (
        selected.pod_count.astype(float) - low) / (high - low)
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["replay_second", "source_time", "source_value", "target_rps"])
        for index, (_, row) in enumerate(selected.iterrows()):
            writer.writerow([index * BIN_SECONDS, row.timestamp, int(row.pod_count), float(row.target_rps)])
    replay = pd.read_csv(TRACE)
    frozen_schedule = schedule(replay)
    measurement_requests = len(frozen_schedule) - 4 * WARMUP
    plan = {
        "schema_version": 1,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_label": "lower-intensity resource-guarded D1 chaotic variant",
        "scientific_separation": "New intensity variant; never pool with or relabel the hazardous 20-120 RPS experiment.",
        "source_path": str(source.relative_to(ROOT)), "source_sha256": sha256(source),
        "selected_indices_inclusive": [start, stop_inclusive],
        "selection_provenance": "Reuses the prior controller-independent D1 scenario/window selection only; no old outcomes entered the new affine mapping.",
        "replay_path": str(TRACE.relative_to(ROOT)), "replay_sha256": sha256(TRACE),
        "expected_schedule_sha256": schedule_hash(frozen_schedule),
        "transformation": {
            "formula": f"target_rps = {MIN_RPS:g} + {MAX_RPS-MIN_RPS:g} * (pod_count - {low:g}) / ({high:g} - {low:g})",
            "minimum_rps": MIN_RPS, "maximum_rps": MAX_RPS,
            "relative_fluctuations": "Affine mapping preserves order, normalized deviations, extrema locations, and relative range position.",
            "time_mapping": "Each 900-second source observation is held for one 10-second replay bin (90x acceleration).",
            "warmup_seconds": WARMUP, "warmup_rps": 4, "measurement_seconds": DURATION,
            "request_timeout_seconds": 5, "maximum_in_flight": 256,
            "scheduled_measurement_requests": measurement_requests,
        },
        "resource_policy": "configs/guarded_chaotic_safety.json",
        "application": {"image": "php:8.2-apache", "cpu_request": "200m", "cpu_limit": "500m",
                        "memory_request": "64Mi", "memory_limit": "128Mi", "replica_bounds": [1, 20]},
        "acceptance_thresholds_unchanged": {"complete_schedule": True, "generator_drops": 0,
            "p99_dispatch_delay_below_seconds": .1, "cpu_coverage_at_least": .90,
            "max_metric_gap_below_seconds": 15, "controller_exclusive": True,
            "measurement_window_bracketed": True, "scaling_response_observed": True},
        "order": ["calibrated_hpa", "holtwinters", "strawman_hpa"],
    }
    runs = [{"sequence": index + 1, "dataset": "chaotic_guarded_d1_s1", "arm": arm,
             "repeat": 1, "warmup": WARMUP, "duration": DURATION,
             "category": "guarded_chaotic_comparison", "max_inflight": 256}
            for index, arm in enumerate(plan["order"])]
    plan["runs"] = runs
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frozen_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (OUT / "run_plan.json").write_text(json.dumps(runs, indent=2) + "\n")
    (OUT / "WORKLOAD_TRANSFORMATION.md").write_text(
        "# Guarded chaotic workload transformation\n\n"
        f"This is a new, lower-intensity variant of the D1 window at `{source.relative_to(ROOT)}` "
        f"(rows {start}–{stop_inclusive}). It uses `{plan['transformation']['formula']}`, retaining the "
        "same 42 bins, their order, and 90× time compression. The exact replay and request schedule were "
        f"frozen before any controller run: replay SHA-256 `{sha256(TRACE)}`; schedule SHA-256 "
        f"`{plan['expected_schedule_sha256']}`; {measurement_requests} measurement requests. The hard ceilings "
        "are 45 RPS and 256 in flight, with the existing five-second timeout, 120-second warmup, and "
        "420-second measurement. Results are not replicates of the prior 20–120 RPS variant.\n")
    (OUT / "REPRODUCE.md").write_text(
        "# Reproduce the guarded chaotic comparison\n\n"
        "```bash\n.venv/bin/python scripts/live/prepare_guarded_chaotic_comparison.py\n"
        ".venv/bin/python scripts/live/preflight_guarded_chaotic.py\n"
        ".venv/bin/python scripts/live/run_guarded_chaotic_comparison.py\n"
        ".venv/bin/python scripts/live/verify_guarded_chaotic_comparison.py\n```\n")
    print(json.dumps({"decision": "PASS", "trace_sha256": sha256(TRACE),
                      "schedule_sha256": plan["expected_schedule_sha256"],
                      "measurement_requests": measurement_requests}, indent=2))


if __name__ == "__main__":
    main()
