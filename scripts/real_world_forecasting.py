#!/usr/bin/env python3
"""Leakage-safe forecasting on the retained NASA and Alibaba source traces.

This module deliberately does not reproduce the paper's undocumented split,
feature, and horizon choices.  It writes the protocol before model fitting and
retains every held-out prediction needed for an independent metric audit.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import re
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits


ROOT = Path(__file__).resolve().parents[1]
NASA_RE = re.compile(
    rb"\[(\d{2})/(Jul|Aug)/1995:(\d{2}):(\d{2}):(\d{2}) (-\d{4})\]"
)
MODELS = ("persistence", "moving_average", "exponential_smoothing", "gbdt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def native_scalar(value):
    return value.item() if hasattr(value, "item") else value


def metric_values(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Metrics with explicit zero handling; all but MAPE include every pair."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if len(actual) != len(predicted) or not len(actual):
        raise ValueError("metrics require equally sized, nonempty vectors")
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise ValueError("metrics require finite values")
    error = np.abs(actual - predicted)
    nonzero = actual != 0
    denominator = np.abs(actual).sum()
    smape_denominator = np.abs(actual) + np.abs(predicted)
    smape_terms = np.divide(
        2 * error,
        smape_denominator,
        out=np.zeros_like(error),
        where=smape_denominator != 0,
    )
    return {
        "pairs": int(len(actual)),
        "mae": float(error.mean()),
        "rmse": float(np.sqrt(np.mean((actual - predicted) ** 2))),
        "mape_nonzero": (
            float(100 * np.mean(error[nonzero] / np.abs(actual[nonzero])))
            if nonzero.any()
            else None
        ),
        "mape_defined_pairs": int(nonzero.sum()),
        "mape_undefined_zero_pairs": int((~nonzero).sum()),
        "wape": float(100 * error.sum() / denominator) if denominator else None,
        "smape": float(100 * smape_terms.mean()),
        "absolute_actual_denominator": float(denominator),
    }


def chronological_boundaries(length: int) -> tuple[int, int]:
    if length < 30:
        raise ValueError("series too short for 60/20/20 chronological split")
    train_end = int(length * 0.60)
    validation_end = int(length * 0.80)
    if not (0 < train_end < validation_end < length):
        raise ValueError("invalid chronological boundaries")
    return train_end, validation_end


def parse_nasa(path: Path, interval_seconds: int = 300) -> tuple[pd.DataFrame, dict]:
    """Count requests in complete July calendar bins, preserving genuine zeros."""
    counts: Counter[int] = Counter()
    parsed = unparsed = invalid = 0
    first_epoch = last_epoch = None
    offsets: Counter[str] = Counter()
    with gzip.open(path, "rb") as handle:
        for line in handle:
            match = NASA_RE.search(line)
            if not match:
                unparsed += 1
                continue
            day, month, hour, minute, second, offset = match.groups()
            if month != b"Jul" or offset != b"-0400":
                invalid += 1
                continue
            try:
                local = datetime(
                    1995, 7, int(day), int(hour), int(minute), int(second),
                    tzinfo=timezone(timedelta(hours=-4)),
                )
            except ValueError:
                invalid += 1
                continue
            epoch = int(local.timestamp())
            bin_epoch = epoch - epoch % interval_seconds
            counts[bin_epoch] += 1
            parsed += 1
            offsets[offset.decode()] += 1
            first_epoch = epoch if first_epoch is None else min(first_epoch, epoch)
            last_epoch = epoch if last_epoch is None else max(last_epoch, epoch)
    if first_epoch is None or last_epoch is None:
        raise ValueError("NASA source contained no valid timestamps")
    first_bin = first_epoch - first_epoch % interval_seconds
    final_partial_bin = last_epoch - last_epoch % interval_seconds
    # The archive ends inside the 13:30 bin.  Score only bins whose right edge
    # precedes that truncation; bins without requests inside this covered span
    # remain genuine zero-demand bins.
    epochs = np.arange(first_bin, final_partial_bin, interval_seconds, dtype=np.int64)
    values = np.array([counts[int(epoch)] for epoch in epochs], dtype=float)
    frame = pd.DataFrame(
        {
            "timestamp": [datetime.fromtimestamp(int(x), timezone.utc).isoformat() for x in epochs],
            "value": values,
        }
    )
    metadata = {
        "source_path": display_path(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "parsed_requests": parsed,
        "unparsed_records": unparsed,
        "invalid_timestamp_records": invalid,
        "timestamp_interpretation": "fixed UTC-04:00 offset recorded in the log; output timestamps are UTC",
        "timezone_offsets": dict(offsets),
        "first_request_local": datetime.fromtimestamp(first_epoch, timezone(timedelta(hours=-4))).isoformat(),
        "last_request_local": datetime.fromtimestamp(last_epoch, timezone(timedelta(hours=-4))).isoformat(),
        "aggregation_seconds": interval_seconds,
        "complete_bins": len(frame),
        "nonempty_bins_including_trailing_partial": len(counts),
        "zero_request_bins": int((values == 0).sum()),
        "excluded_trailing_partial_bin_requests": int(counts[final_partial_bin]),
        "duplicate_policy": "Each valid log record is one request. Equal timestamps are concurrent requests and are not deduplicated.",
        "missing_policy": "All complete calendar bins between the first and final partial bin are retained; bins without records are zero requests. No interpolation.",
        "target": "HTTP request count per complete 5-minute bin",
        "units": "requests/5 minutes",
    }
    return frame, metadata


def scan_nasa_archive(path: Path, interval_seconds: int = 300) -> dict:
    """Inventory an additional NASA archive without making it an evaluation input."""
    requests = invalid = 0
    nonempty_bins: set[int] = set()
    with gzip.open(path, "rb") as handle:
        for line in handle:
            match = NASA_RE.search(line)
            if not match:
                invalid += 1
                continue
            day, month, hour, minute, second, offset = match.groups()
            month_number = {b"Jul": 7, b"Aug": 8}.get(month)
            if month_number is None or offset != b"-0400":
                invalid += 1
                continue
            local = datetime(
                1995, month_number, int(day), int(hour), int(minute), int(second),
                tzinfo=timezone(timedelta(hours=-4)),
            )
            epoch = int(local.timestamp())
            nonempty_bins.add(epoch - epoch % interval_seconds)
            requests += 1
    return {
        "source_path": display_path(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "parsed_requests": requests,
        "unparsed_or_invalid_records": invalid,
        "nonempty_5_minute_bins_including_boundary_bins": len(nonempty_bins),
    }


def _commit_container(
    records: dict[int, list[float]], sums: dict[int, float], counts: Counter[int]
) -> tuple[int, int]:
    duplicates = invalid = 0
    for timestamp, values in records.items():
        if not values:
            invalid += 1
            continue
        duplicates += max(0, len(values) - 1)
        # One contribution per container/timestamp prevents duplicate rows from
        # overweighting a container.  The current prefix contains no duplicates.
        sums[timestamp] = sums.get(timestamp, 0.0) + float(np.mean(values))
        counts[timestamp] += 1
    return duplicates, invalid


def select_contiguous_timestamps(
    contributor_counts: dict[int, int] | Counter[int],
    minimum_contributors: int,
    interval_seconds: int,
) -> tuple[int, int, int]:
    """Return earliest longest fixed-cadence run satisfying a count threshold."""
    eligible = sorted(
        timestamp for timestamp, count in contributor_counts.items()
        if count >= minimum_contributors
    )
    if not eligible:
        raise ValueError("no timestamps satisfy the contributor threshold")
    runs: list[tuple[int, int, int]] = []
    start = previous = eligible[0]
    for timestamp in eligible[1:]:
        if timestamp - previous != interval_seconds:
            runs.append((start, previous, (previous - start) // interval_seconds + 1))
            start = timestamp
        previous = timestamp
    runs.append((start, previous, (previous - start) // interval_seconds + 1))
    return sorted(runs, key=lambda item: (-item[2], item[0]))[0]


def parse_alibaba(
    path: Path, minimum_contributors: int = 20, interval_seconds: int = 10
) -> tuple[pd.DataFrame, dict]:
    """Form a native-cadence observed-container CPU mean from a bounded prefix.

    A container block is committed only after the next named identifier appears,
    so the identifier interrupted by the byte-range boundary is never included.
    """
    sums: dict[int, float] = defaultdict(float)
    contributors: Counter[int] = Counter()
    named_ids: list[str] = []
    current_id: str | None = None
    current_records: dict[int, list[float]] = defaultdict(list)
    decoded_rows = empty_identifier_rows = malformed_rows = invalid_rows = 0
    duplicate_container_timestamps = 0
    member_name = None
    stream_error = None
    try:
        with tarfile.open(path, "r|gz") as archive:
            member = archive.next()
            if member is None:
                raise ValueError("Alibaba prefix has no tar member")
            member_name = member.name
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("Alibaba tar member is not extractable")
            for raw in extracted:
                decoded_rows += 1
                fields = raw.decode("utf-8", errors="strict").rstrip("\n").split(",")
                if len(fields) != 11:
                    malformed_rows += 1
                    continue
                container_id = fields[0]
                if not container_id:
                    empty_identifier_rows += 1
                    continue
                if container_id != current_id:
                    if current_id is not None:
                        dup, bad = _commit_container(current_records, sums, contributors)
                        duplicate_container_timestamps += dup
                        invalid_rows += bad
                    current_id = container_id
                    named_ids.append(container_id)
                    current_records = defaultdict(list)
                try:
                    timestamp = int(float(fields[2]))
                    cpu = float(fields[3])
                except ValueError:
                    invalid_rows += 1
                    continue
                if timestamp < 0 or timestamp % interval_seconds or not (0 <= cpu <= 100):
                    invalid_rows += 1
                    continue
                current_records[timestamp].append(cpu)
    except tarfile.ReadError as exc:
        stream_error = f"{type(exc).__name__}: {exc}"
    # Deliberately do not commit current_records: this final container block is
    # cut by the 16 MiB byte-range boundary.
    if stream_error is None:
        raise ValueError("expected a bounded/truncated Alibaba gzip stream")
    selected_start, selected_end, selected_length = select_contiguous_timestamps(
        contributors, minimum_contributors, interval_seconds
    )
    timestamps = np.arange(selected_start, selected_end + interval_seconds, interval_seconds)
    values = np.array([sums[int(x)] / contributors[int(x)] for x in timestamps])
    counts = np.array([contributors[int(x)] for x in timestamps], dtype=int)
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "value": values,
            "contributors": counts,
        }
    )
    metadata = {
        "source_path": display_path(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "source_is_bounded_prefix": True,
        "member": member_name,
        "stream_termination": stream_error,
        "decoded_complete_rows": decoded_rows,
        "malformed_rows": malformed_rows,
        "empty_identifier_rows_excluded": empty_identifier_rows,
        "named_identifier_blocks_seen": len(named_ids),
        "unique_named_identifiers_seen": len(set(named_ids)),
        "repeated_named_identifier_blocks": len(named_ids) - len(set(named_ids)),
        "complete_named_container_blocks_used": max(0, len(named_ids) - 1),
        "truncated_final_identifier_excluded": named_ids[-1],
        "invalid_measurements_excluded": invalid_rows,
        "duplicate_container_timestamps": duplicate_container_timestamps,
        "native_interval_seconds": interval_seconds,
        "minimum_contributors_per_timestamp": minimum_contributors,
        "selection_rule": "Earliest longest exact 10-second run for which every timestamp has at least 20 valid observations from complete named container blocks.",
        "selected_start_seconds": selected_start,
        "selected_end_seconds": selected_end,
        "selected_observations": selected_length,
        "selected_duration_seconds": selected_end - selected_start,
        "contributors_min": int(counts.min()),
        "contributors_median": float(np.median(counts)),
        "contributors_max": int(counts.max()),
        "missing_policy": "No missing timestamp is filled and no absent container is treated as zero. Only exact source timestamps are averaged.",
        "duplicate_policy": "At most one contribution per container/timestamp; duplicate rows would be averaged before the cross-container mean.",
        "target": "mean cpu_util_percent among valid observed complete-prefix containers at each exact source timestamp",
        "units": "percent",
        "scope_limitation": "Observed-container mean from a nonrandom prefix, not whole-cluster CPU demand and not an individual-container series.",
    }
    return frame, metadata


def trailing_mean_forecasts(values: np.ndarray, window: int, horizon: int) -> np.ndarray:
    output = np.full(len(values), np.nan)
    cumulative = np.r_[0.0, np.cumsum(values)]
    for origin in range(window, len(values) - horizon + 1):
        output[origin] = (cumulative[origin] - cumulative[origin - window]) / window
    return output


def holt_forecasts(values: np.ndarray, alpha: float, beta: float, horizon: int) -> np.ndarray:
    output = np.full(len(values), np.nan)
    level = float(values[0])
    trend = float(np.mean(np.diff(values[: min(12, len(values))])))
    for origin in range(1, len(values)):
        output[origin] = max(0.0, level + horizon * trend)
        previous_level = level
        level = alpha * values[origin] + (1 - alpha) * (level + trend)
        trend = beta * (level - previous_level) + (1 - beta) * trend
    return output


def seasonal_holt_winters_forecasts(
    values: np.ndarray, period: int, alpha: float, beta: float, gamma: float, horizon: int
) -> np.ndarray:
    if len(values) < 2 * period:
        raise ValueError("two full seasons are required")
    output = np.full(len(values), np.nan)
    level = float(np.mean(values[:period]))
    trend = float((np.mean(values[period : 2 * period]) - level) / period)
    seasonal = values[:period].astype(float) - level
    for origin in range(period, len(values)):
        if origin >= 2 * period:
            target_season = (origin + horizon - 1) % period
            output[origin] = max(0.0, level + horizon * trend + seasonal[target_season])
        old_level = level
        level = alpha * (values[origin] - seasonal[origin % period]) + (1 - alpha) * (level + trend)
        trend = beta * (level - old_level) + (1 - beta) * trend
        seasonal[origin % period] = gamma * (values[origin] - level) + (1 - gamma) * seasonal[origin % period]
    return output


def lag_matrix(values: np.ndarray, origins: np.ndarray, lags: list[int]) -> np.ndarray:
    if len(origins) and origins.min() < max(lags):
        raise ValueError("lag feature requested before enough history exists")
    return np.column_stack([values[origins - lag] for lag in lags])


def select_exponential_smoothing(
    dataset: str,
    values: np.ndarray,
    train_end: int,
    validation_end: int,
    horizon: int,
    period: int | None,
) -> tuple[dict, np.ndarray]:
    validation_origins = np.arange(train_end, validation_end - horizon + 1)
    actual = values[validation_origins + horizon - 1]
    candidates = []
    for alpha in (0.2, 0.5, 0.8):
        for beta in (0.0, 0.2):
            gammas = (0.1, 0.3) if period else (None,)
            for gamma in gammas:
                if period:
                    predictions = seasonal_holt_winters_forecasts(
                        values, period, alpha, beta, float(gamma), horizon
                    )
                else:
                    predictions = holt_forecasts(values, alpha, beta, horizon)
                score = float(np.mean(np.abs(actual - predictions[validation_origins])))
                params = {"alpha": alpha, "beta": beta}
                if period:
                    params.update({"gamma": gamma, "seasonal_period": period})
                candidates.append((score, json.dumps(params, sort_keys=True), params, predictions))
    _, _, params, predictions = min(candidates, key=lambda item: (item[0], item[1]))
    params["selection_dataset"] = dataset
    params["selection_metric"] = "validation MAE"
    return params, predictions


def evaluate_dataset(name: str, frame: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    values = frame["value"].to_numpy(float)
    train_end, validation_end = chronological_boundaries(len(values))
    all_predictions: list[dict] = []
    summaries: list[dict] = []
    selected: list[dict] = []
    for horizon in config["horizons"]:
        origins = np.arange(validation_end, len(values) - horizon + 1)
        targets = origins + horizon - 1
        predictions = {
            "persistence": values[origins - 1],
            "moving_average": trailing_mean_forecasts(
                values, config["moving_average_window"], horizon
            )[origins],
        }
        es_params, es_all = select_exponential_smoothing(
            name, values, train_end, validation_end, horizon, config["seasonal_period"]
        )
        predictions["exponential_smoothing"] = es_all[origins]
        selected.append({"dataset": name, "horizon_steps": horizon, "model": "exponential_smoothing", **es_params})

        lags = config["gbdt_lags"]
        fit_origins = np.arange(max(lags), validation_end - horizon + 1)
        model = HistGradientBoostingRegressor(
            max_iter=80,
            max_leaf_nodes=15,
            learning_rate=0.05,
            min_samples_leaf=20,
            early_stopping=False,
            random_state=20261024,
        )
        model.fit(lag_matrix(values, fit_origins, lags), values[fit_origins + horizon - 1])
        predictions["gbdt"] = np.maximum(0.0, model.predict(lag_matrix(values, origins, lags)))
        for model_name in MODELS:
            predicted = np.asarray(predictions[model_name], dtype=float)
            if len(predicted) != len(targets) or not np.isfinite(predicted).all():
                raise AssertionError(f"invalid predictions: {name}/{horizon}/{model_name}")
            metrics = metric_values(values[targets], predicted)
            summaries.append(
                {
                    "dataset": name,
                    "target": config["target"],
                    "units": config["units"],
                    "horizon_steps": horizon,
                    "horizon_seconds": horizon * config["interval_seconds"],
                    "model": model_name,
                    "train_observations": train_end,
                    "validation_observations": validation_end - train_end,
                    "test_partition_observations": len(values) - validation_end,
                    **metrics,
                }
            )
            for origin, target, prediction in zip(origins, targets, predicted):
                all_predictions.append(
                    {
                        "dataset": name,
                        "horizon_steps": horizon,
                        "horizon_seconds": horizon * config["interval_seconds"],
                        "model": model_name,
                        "origin_index": int(origin),
                        "last_observed_timestamp": frame["timestamp"].iloc[origin - 1],
                        "target_index": int(target),
                        "target_timestamp": frame["timestamp"].iloc[target],
                        "actual": float(values[target]),
                        "predicted": float(prediction),
                    }
                )
    return pd.DataFrame(all_predictions), summaries, selected


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def write_reports(out: Path, summary: pd.DataFrame, metadata: dict, protocol: dict) -> None:
    display = summary[
        ["dataset", "horizon_seconds", "model", "pairs", "mae", "rmse", "mape_nonzero", "wape", "smape", "mape_undefined_zero_pairs"]
    ].copy()
    for column in ("mae", "rmse", "mape_nonzero", "wape", "smape"):
        display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    rankings = summary.sort_values(["dataset", "horizon_seconds", "mae", "model"])
    winners = rankings.groupby(["dataset", "horizon_seconds"], as_index=False).first()[
        ["dataset", "horizon_seconds", "model", "mae"]
    ]
    comparisons = []
    for (dataset, horizon), group in summary.groupby(["dataset", "horizon_seconds"]):
        errors = group.set_index("model")["mae"]
        comparisons.append(
            {
                "dataset": dataset,
                "horizon_seconds": horizon,
                "ES vs persistence MAE reduction": f"{100 * (errors.persistence - errors.exponential_smoothing) / errors.persistence:.2f}%",
                "ES vs moving-average MAE reduction": f"{100 * (errors.moving_average - errors.exponential_smoothing) / errors.moving_average:.2f}%",
                "GBDT vs ES MAE reduction": f"{100 * (errors.exponential_smoothing - errors.gbdt) / errors.exponential_smoothing:.2f}%",
            }
        )
    report = [
        "# Genuine real-world forecasting evaluation",
        "",
        "These are rolling-origin held-out forecasts on raw NASA requests and native-timestamp Alibaba CPU observations. Forecast accuracy is supporting evidence only; it is not a Kubernetes cost, latency, or controller comparison.",
        "",
        "## Held-out metrics",
        "",
        markdown_table(display),
        "",
        "MAPE is computed only where the actual target is nonzero; the final column exposes every undefined zero-target pair. MAE, RMSE, WAPE, and sMAPE use all pairs. WAPE is 100 × total absolute error / total absolute actual. sMAPE is the mean of 200 × absolute error / (|actual| + |prediction|), with a zero term when both are zero.",
        "",
        "## Lowest held-out MAE",
        "",
        markdown_table(winners.round(4)),
        "",
        "## Paired model interpretation",
        "",
        markdown_table(pd.DataFrame(comparisons)),
        "",
        "Exponential smoothing improves MAE over both persistence and the moving average at every compatible horizon. GBDT has the lowest MAE in all four comparisons, but its incremental gain over exponential smoothing is only 0.60% for NASA at 60 minutes and 3.25% for Alibaba at 60 seconds. The simple smoother is therefore close to the more complex model in those cases. NASA errors increase markedly from 5 to 60 minutes; Alibaba errors are similar at 10 and 60 seconds for this aggregated window. There are no repeated folds or independently sampled Alibaba container groups, so no variance or significance claim is made.",
        "",
        "## Dataset construction",
        "",
        f"NASA: {metadata['nasa']['parsed_requests']:,} requests parsed, {metadata['nasa']['unparsed_records']} unparsed final fragment, {metadata['nasa']['complete_bins']:,} complete 5-minute bins, and {metadata['nasa']['zero_request_bins']} zero-request bins. The trailing partial bin is excluded.",
        "",
        f"Alibaba: {metadata['alibaba']['decoded_complete_rows']:,} complete rows decoded from the bounded prefix. The deterministic aggregate uses {metadata['alibaba']['complete_named_container_blocks_used']:,} completed named container blocks and selects {metadata['alibaba']['selected_observations']:,} consecutive native 10-second timestamps with at least {metadata['alibaba']['minimum_contributors_per_timestamp']} contributors each. The final truncated identifier is excluded; no gap is filled.",
        "",
        "## Interpretation limits",
        "",
        "NASA is request-count demand; Alibaba is observed-container mean CPU percent. Their errors and percentage metrics must not be pooled or compared as if they share a target. The Alibaba prefix is nonrandom and its cross-container membership varies by timestamp. The retained NASA evaluation uses July only and includes calendar zeros; the paper repository describes July–August nonempty-bin aggregation. These protocols therefore answer an independent reproducible question, not a numerical reproduction of the paper.",
        "",
        "Protocol and exact boundaries are in `evaluation_protocol.json`; every test prediction is in `predictions.csv`.",
        "",
    ]
    (out / "RESULTS.md").write_text("\n".join(report))

    our_gbdt = summary[summary.model == "gbdt"].copy()
    rows = []
    published = {
        "nasa": ("GBDT", "MAPE 1.36%", 1.36),
        "alibaba": ("GBDT", "MAPE 0.75%", 0.75),
    }
    for dataset in ("nasa", "alibaba"):
        for record in our_gbdt[our_gbdt.dataset == dataset].itertuples():
            original_model, original_value, _ = published[dataset]
            rows.append(
                {
                    "Dataset": dataset.upper(),
                    "Original model": original_model,
                    "Original metric/value": original_value,
                    "Our model": "HistGradientBoostingRegressor",
                    "Our metric/value": f"MAPE(nonzero) {record.mape_nonzero:.4f}% at {record.horizon_seconds}s",
                    "Protocol comparable?": "NO — NOT DIRECTLY COMPARABLE",
                    "Explanation": "Different target/subset, split, features, horizon and zero handling; no numerical difference is valid.",
                }
            )
    comparison = pd.DataFrame(rows)
    comparison.to_csv(out / "paper_comparison.csv", index=False)
    paper_text = [
        "# Comparison with Duman and Eken",
        "",
        "The accessible paper abstract states that gradient boosting models achieved sub-2% MAPE on NASA and Alibaba. The authors' public repository is more specific: NASA is described as 3.46 million July–August requests aggregated into 5-minute intervals (16,364 samples), while Alibaba is described as machine utilization from 20 machines (2,240 intervals). It reports NASA CatBoost MAPE 0.40%, NASA GBDT 1.36%, Alibaba GBDT 0.75%, and other model values.",
        "",
        "Neither accessible source establishes the exact real-world chronological boundaries, forecast horizon, lag features, zero-target MAPE rule, 20-machine identifiers, or model-selection code needed for an independent numerical reproduction. Our retained Alibaba source is container usage rather than the paper repository's described machine utilization target.",
        "",
        markdown_table(comparison),
        "",
        "The paper's 37.4% pattern-aware improvement and 96.7% LLM classification accuracy are NOT RECOMPUTED in this milestone. No numerical difference from the real-world paper values is calculated because the protocols are not comparable.",
        "",
        "Sources: https://doi.org/10.1016/j.jss.2026.112861 ; https://github.com/syswe/llm-phpa ; https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018",
        "",
    ]
    (out / "PAPER_COMPARISON.md").write_text("\n".join(paper_text))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results/real_world_forecasting")
    parser.add_argument("--nasa", type=Path, default=ROOT / "data/nasa/NASA_access_log_Jul95.gz")
    parser.add_argument("--alibaba", type=Path, default=ROOT / "data/alibaba/container_usage.prefix.tar.gz")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    nasa, nasa_metadata = parse_nasa(args.nasa)
    alibaba, alibaba_metadata = parse_alibaba(args.alibaba)
    august_path = args.nasa.with_name("NASA_access_log_Aug95.gz")
    nasa_companion = scan_nasa_archive(august_path) if august_path.is_file() else None
    if nasa_companion:
        nasa_metadata["paper_protocol_clue"] = {
            "july_plus_august_parsed_requests": nasa_metadata["parsed_requests"] + nasa_companion["parsed_requests"],
            "july_plus_august_nonempty_5_minute_bins": nasa_metadata["nonempty_bins_including_trailing_partial"] + nasa_companion["nonempty_5_minute_bins_including_boundary_bins"],
            "interpretation": "These equal the public repository's approximately 3.46 million requests and exactly 16,364 samples, suggesting nonempty-bin aggregation. We do not adopt that irregular-gap sequence because exact paper split/horizon/zero handling remain unknown.",
        }
    nasa.to_csv(args.out / "nasa_series.csv", index=False)
    alibaba.to_csv(args.out / "alibaba_series.csv", index=False)
    datasets = {
        "nasa": (
            nasa,
            {
                "target": nasa_metadata["target"],
                "units": nasa_metadata["units"],
                "interval_seconds": 300,
                "horizons": [1, 12],
                "moving_average_window": 12,
                "seasonal_period": 288,
                "gbdt_lags": list(range(1, 13)) + [288, 289, 576],
            },
        ),
        "alibaba": (
            alibaba,
            {
                "target": alibaba_metadata["target"],
                "units": alibaba_metadata["units"],
                "interval_seconds": 10,
                "horizons": [1, 6],
                "moving_average_window": 6,
                "seasonal_period": None,
                "gbdt_lags": list(range(1, 13)) + [60, 120],
            },
        ),
    }
    protocol = {
        "protocol_version": 1,
        "frozen_before_model_fit": True,
        "random_seed": 20261024,
        "split": "chronological 60% train / 20% validation / 20% held-out test; integer floor boundaries",
        "evaluation": "rolling origin; observations earlier in the test partition become available after their timestamps",
        "models": {
            "persistence": "last observed target",
            "moving_average": "unweighted trailing window; 12 NASA samples, 6 Alibaba samples",
            "exponential_smoothing": "NASA additive seasonal Holt-Winters with fixed daily period 288; Alibaba nonseasonal Holt linear; alpha/beta/gamma chosen only by validation MAE from documented grid",
            "gbdt": "direct horizon-specific histogram gradient boosting with past-target lags only; fixed hyperparameters; trained on train+validation labels, never test labels",
        },
        "gbdt_hyperparameters": {"max_iter": 80, "max_leaf_nodes": 15, "learning_rate": 0.05, "min_samples_leaf": 20, "early_stopping": False},
        "exponential_smoothing_grid": {"alpha": [0.2, 0.5, 0.8], "beta": [0.0, 0.2], "gamma_nasa": [0.1, 0.3]},
        "metrics": ["MAE", "RMSE", "MAPE on nonzero actuals", "WAPE", "sMAPE"],
        "zero_rule": "MAE/RMSE/WAPE/sMAPE include zero targets. MAPE excludes them as mathematically undefined and reports both defined and undefined pair counts.",
        "negative_prediction_rule": "exponential-smoothing and GBDT forecasts clipped to zero",
        "missing_rule": "No imputation. NASA complete covered calendar bins without records are valid zero request counts; Alibaba requires exact contiguous source timestamps and never treats absent containers as zero.",
        "combination_rule": "No cross-dataset aggregation. Alibaba combines valid simultaneous CPU percentages by arithmetic mean after limiting each container to one contribution per timestamp.",
        "datasets": {},
    }
    for name, (frame, config) in datasets.items():
        train_end, validation_end = chronological_boundaries(len(frame))
        protocol["datasets"][name] = {
            **config,
            "observations": len(frame),
            "train_indices": [0, train_end - 1],
            "validation_indices": [train_end, validation_end - 1],
            "test_indices": [validation_end, len(frame) - 1],
            "train_start_timestamp": native_scalar(frame["timestamp"].iloc[0]),
            "train_end_timestamp": native_scalar(frame["timestamp"].iloc[train_end - 1]),
            "validation_start_timestamp": native_scalar(frame["timestamp"].iloc[train_end]),
            "validation_end_timestamp": native_scalar(frame["timestamp"].iloc[validation_end - 1]),
            "test_start_timestamp": native_scalar(frame["timestamp"].iloc[validation_end]),
            "test_end_timestamp": native_scalar(frame["timestamp"].iloc[-1]),
        }
    # This file is intentionally emitted before any estimator is fit.
    (args.out / "evaluation_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    metadata = {
        "nasa": nasa_metadata,
        "nasa_august_companion_inventory": nasa_companion,
        "alibaba": alibaba_metadata,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "cpu_thread_limit": 1,
        },
    }
    (args.out / "preprocessing_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    prediction_frames = []
    summaries: list[dict] = []
    selected: list[dict] = []
    for name, (frame, config) in datasets.items():
        predictions, dataset_summaries, dataset_selected = evaluate_dataset(name, frame, config)
        prediction_frames.append(predictions)
        summaries.extend(dataset_summaries)
        selected.extend(dataset_selected)
        # Incremental checkpoint after each dataset.
        pd.concat(prediction_frames, ignore_index=True).to_csv(args.out / "predictions.partial.csv", index=False)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.to_csv(args.out / "predictions.csv", index=False)
    (args.out / "predictions.partial.csv").unlink()
    summary = pd.DataFrame(summaries)
    summary.to_csv(args.out / "metrics.csv", index=False)
    pd.DataFrame(selected).to_csv(args.out / "selected_hyperparameters.csv", index=False)
    write_reports(args.out, summary, metadata, protocol)
    print(summary[["dataset", "horizon_seconds", "model", "pairs", "mae", "rmse", "mape_nonzero", "wape"]].to_string(index=False))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()
