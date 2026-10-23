#!/usr/bin/env python3
"""Independent audit of retained real-world forecasting predictions and metrics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float | None, right: float | None, tolerance: float = TOLERANCE) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def independent_metrics(rows: list[dict]) -> dict:
    actual = [float(row["actual"]) for row in rows]
    predicted = [float(row["predicted"]) for row in rows]
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    squared = [(a - p) ** 2 for a, p in zip(actual, predicted)]
    nonzero_terms = [error / abs(a) for a, error in zip(actual, errors) if a != 0]
    denominator = sum(abs(a) for a in actual)
    smape_terms = [0.0 if abs(a) + abs(p) == 0 else 2 * e / (abs(a) + abs(p)) for a, p, e in zip(actual, predicted, errors)]
    return {
        "pairs": len(rows),
        "mae": sum(errors) / len(rows),
        "rmse": math.sqrt(sum(squared) / len(rows)),
        "mape_nonzero": 100 * sum(nonzero_terms) / len(nonzero_terms) if nonzero_terms else None,
        "mape_defined_pairs": len(nonzero_terms),
        "mape_undefined_zero_pairs": len(rows) - len(nonzero_terms),
        "wape": 100 * sum(errors) / denominator if denominator else None,
        "smape": 100 * sum(smape_terms) / len(smape_terms),
        "absolute_actual_denominator": denominator,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/real_world_forecasting")
    args = parser.parse_args()
    out = args.results
    protocol = json.loads((out / "evaluation_protocol.json").read_text())
    preprocessing = json.loads((out / "preprocessing_metadata.json").read_text())
    checks: dict[str, bool] = {}

    checks["protocol_marked_frozen_before_fit"] = protocol["frozen_before_model_fit"] is True
    for dataset in ("nasa", "alibaba"):
        source = ROOT / preprocessing[dataset]["source_path"]
        checks[f"{dataset}_source_exists"] = source.is_file()
        checks[f"{dataset}_source_hash"] = sha256(source) == preprocessing[dataset]["sha256"]
    companion = preprocessing.get("nasa_august_companion_inventory")
    if companion:
        companion_path = ROOT / companion["source_path"]
        checks["nasa_august_companion_exists"] = companion_path.is_file()
        checks["nasa_august_companion_hash"] = sha256(companion_path) == companion["sha256"]

    series = {}
    for dataset in ("nasa", "alibaba"):
        with (out / f"{dataset}_series.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        series[dataset] = rows
        spec = protocol["datasets"][dataset]
        train_end = spec["train_indices"][1] + 1
        validation_end = spec["validation_indices"][1] + 1
        checks[f"{dataset}_series_count"] = len(rows) == spec["observations"]
        checks[f"{dataset}_split_contiguous"] = (
            spec["train_indices"] == [0, train_end - 1]
            and spec["validation_indices"] == [train_end, validation_end - 1]
            and spec["test_indices"] == [validation_end, len(rows) - 1]
            and train_end == int(len(rows) * 0.60)
            and validation_end == int(len(rows) * 0.80)
        )
        interval = spec["interval_seconds"]
        if dataset == "alibaba":
            timestamps = [int(row["timestamp"]) for row in rows]
            checks["alibaba_native_continuity"] = all(right - left == interval for left, right in zip(timestamps, timestamps[1:]))
            checks["alibaba_contributor_floor"] = min(int(row["contributors"]) for row in rows) >= preprocessing[dataset]["minimum_contributors_per_timestamp"]
        else:
            timestamps = [datetime.fromisoformat(row["timestamp"]) for row in rows]
            checks["nasa_calendar_continuity"] = all(int((right - left).total_seconds()) == interval for left, right in zip(timestamps, timestamps[1:]))
            checks["nasa_series_sum"] = int(sum(float(row["value"]) for row in rows)) == preprocessing[dataset]["parsed_requests"] - preprocessing[dataset]["excluded_trailing_partial_bin_requests"]

    with (out / "predictions.csv").open(newline="") as handle:
        predictions = list(csv.DictReader(handle))
    with (out / "metrics.csv").open(newline="") as handle:
        metrics = list(csv.DictReader(handle))
    with (out / "selected_hyperparameters.csv").open(newline="") as handle:
        selected_parameters = list(csv.DictReader(handle))
    expected_selections = {
        (dataset, str(horizon))
        for dataset in ("nasa", "alibaba")
        for horizon in protocol["datasets"][dataset]["horizons"]
    }
    checks["selected_hyperparameters_cover_protocol"] = {
        (row["dataset"], row["horizon_steps"]) for row in selected_parameters
    } == expected_selections
    checks["selected_hyperparameters_within_frozen_grid"] = all(
        float(row["alpha"]) in protocol["exponential_smoothing_grid"]["alpha"]
        and float(row["beta"]) in protocol["exponential_smoothing_grid"]["beta"]
        and (
            row["dataset"] != "nasa"
            or float(row["gamma"]) in protocol["exponential_smoothing_grid"]["gamma_nasa"]
        )
        for row in selected_parameters
    )
    grouped: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    duplicate_keys = set()
    seen = set()
    for row in predictions:
        key = (row["dataset"], int(row["horizon_steps"]), row["model"])
        unique = (*key, int(row["origin_index"]), int(row["target_index"]))
        if unique in seen:
            duplicate_keys.add(unique)
        seen.add(unique)
        grouped[key].append(row)
    checks["prediction_rows_unique"] = not duplicate_keys
    checks["all_metric_groups_present"] = len(grouped) == len(metrics) == 16

    audit_rows = []
    for summary in metrics:
        dataset = summary["dataset"]
        horizon = int(summary["horizon_steps"])
        model = summary["model"]
        rows = sorted(grouped[(dataset, horizon, model)], key=lambda row: int(row["origin_index"]))
        spec = protocol["datasets"][dataset]
        test_start = spec["test_indices"][0]
        expected_origins = list(range(test_start, len(series[dataset]) - horizon + 1))
        actual_origins = [int(row["origin_index"]) for row in rows]
        alignment = actual_origins == expected_origins
        for row in rows:
            origin = int(row["origin_index"])
            target = int(row["target_index"])
            alignment = alignment and target == origin + horizon - 1
            alignment = alignment and row["last_observed_timestamp"] == series[dataset][origin - 1]["timestamp"]
            alignment = alignment and row["target_timestamp"] == series[dataset][target]["timestamp"]
            alignment = alignment and close(float(row["actual"]), float(series[dataset][target]["value"]))
        checks[f"alignment_{dataset}_{horizon}_{model}"] = alignment
        recomputed = independent_metrics(rows)
        consistent = True
        for field, value in recomputed.items():
            saved_text = summary[field]
            saved = None if saved_text == "" else float(saved_text)
            consistent = consistent and close(saved, value)
        checks[f"metrics_{dataset}_{horizon}_{model}"] = consistent
        audit_rows.append({"dataset": dataset, "horizon_steps": horizon, "model": model, **recomputed, "consistent": consistent})

    # Every model must use exactly the same targets within a dataset/horizon.
    for dataset in ("nasa", "alibaba"):
        for horizon in protocol["datasets"][dataset]["horizons"]:
            signatures = []
            for model in ("persistence", "moving_average", "exponential_smoothing", "gbdt"):
                rows = sorted(grouped[(dataset, horizon, model)], key=lambda row: int(row["origin_index"]))
                signatures.append([(row["target_index"], row["target_timestamp"], row["actual"]) for row in rows])
            checks[f"common_targets_{dataset}_{horizon}"] = all(signature == signatures[0] for signature in signatures[1:])

    report = {
        "verifier": "independent csv/stdlib implementation; does not import the evaluator's metric functions",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "metric_audit": audit_rows,
        "prediction_rows": len(predictions),
        "metric_groups": len(metrics),
        "evidence_files_hashed": len([path for path in out.iterdir() if path.is_file() and path.name != "evidence_manifest.json"]),
    }
    (out / "independent_verification.json").write_text(json.dumps(report, indent=2) + "\n")
    evidence = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "evidence_manifest.json":
            evidence.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "source_hashes": {
            "nasa_july": preprocessing["nasa"]["sha256"],
            "nasa_august_companion": companion["sha256"] if companion else None,
            "alibaba_prefix": preprocessing["alibaba"]["sha256"],
        },
        "files": evidence,
    }
    (out / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checks": len(checks), "prediction_rows": len(predictions), "metric_groups": len(metrics)}, indent=2))
    if report["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        raise SystemExit("verification failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
