#!/usr/bin/env python3
"""Audit the bounded Alibaba archive prefix without treating it as a full archive."""

import csv
import hashlib
import json
import statistics
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/alibaba/container_usage.prefix.tar.gz"
TRACE = ROOT / "data/live_traces/alibaba.csv"
OUT = ROOT / "results/live_trace_phase/alibaba_first_comparison"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe_gaps(values):
    gaps = [right - left for left, right in zip(values, values[1:])]
    longest = current = 1
    for gap in gaps:
        current = current + 1 if gap == 10 else 1
        longest = max(longest, current)
    return {
        "minimum_seconds": min(gaps),
        "median_seconds": statistics.median(gaps),
        "mean_seconds": statistics.mean(gaps),
        "maximum_seconds": max(gaps),
        "longest_10_second_cadence_run_observations": longest,
        "gap_frequency_seconds": {str(int(key)): count for key, count in sorted(Counter(gaps).items())},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    times = {}
    cpu = {}
    identifier_order = []
    transitions = []
    previous = None
    decoded_rows = malformed_rows = 0
    stream_end = None
    member_name = None
    member_size = None
    try:
        with tarfile.open(SOURCE, "r|gz") as archive:
            member = archive.next()
            member_name, member_size = member.name, member.size
            for raw in archive.extractfile(member):
                decoded_rows += 1
                row = raw.decode().rstrip("\n").split(",")
                if len(row) != 11:
                    malformed_rows += 1
                    continue
                identifier = row[0] or "<empty>"
                if identifier != previous:
                    identifier_order.append(identifier)
                    transitions.append((previous, identifier, decoded_rows))
                    previous = identifier
                counts[identifier] += 1
                times.setdefault(identifier, []).append(float(row[2]))
                cpu.setdefault(identifier, []).append(float(row[3]))
    except tarfile.ReadError as exc:
        stream_end = {"type": type(exc).__name__, "message": str(exc)}

    with TRACE.open() as handle:
        replay = list(csv.DictReader(handle))
    selected_times = [float(row["source_time"]) for row in replay]
    selected_cpu = [float(row["source_value"]) for row in replay]
    target_rps = [float(row["target_rps"]) for row in replay]
    replay_seconds = [float(row["replay_second"]) for row in replay]
    c1_times = sorted(times["c_1"])
    c1_cpu = cpu["c_1"]
    available_ids = sorted(identifier for identifier in counts if identifier != "<empty>")
    (OUT / "available_container_ids.txt").write_text("\n".join(available_ids) + "\n")

    checks = {
        "expected_prefix_sha256": sha256(SOURCE) == "726e6240926dc2d7ba53cdfb88a91be8564d124d88d4dec1391e9f745e0a2988",
        "expected_member": member_name == "container_usage.csv",
        "stream_is_bounded_prefix": stream_end is not None and SOURCE.stat().st_size == 16777216,
        "c1_single_stored_block_before_c10": identifier_order.count("c_1") == 1 and "c_10" in identifier_order,
        "c1_timestamps_unique_and_strict": len(set(c1_times)) == len(c1_times) and all(right > left for left, right in zip(times["c_1"], times["c_1"][1:])),
        "c1_cpu_schema_range": all(0 <= value <= 100 for value in c1_cpu),
        "selected_42_rows": len(replay) == 42,
        "selected_is_first_42_c1": selected_times == c1_times[:42] and selected_cpu == c1_cpu[:42],
        "replay_index_is_10_seconds": replay_seconds == [index * 10 for index in range(42)],
        "normalization_is_frozen_formula": all(abs(rate - 120 * value / 58) < 1e-12 for rate, value in zip(target_rps, selected_cpu)),
        "scheduled_measurement_count": sum(round(rate * 10) for rate in target_rps) == 14420,
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_WITH_SEVERE_LIMITATIONS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "experiment_label": "Alibaba-trace-derived demand replay on a benchmark Kubernetes service.",
        "release": "Alibaba Cluster Trace v2018",
        "official_documentation": "https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018",
        "source_url": "https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/container_usage.tar.gz",
        "official_full_archive_sha256": "b4bd3b1b82f5407c1b0dd47fe736ff5152c4b016a9c30cb26f988e2d1c5e5031",
        "source_prefix": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": sha256(SOURCE),
            "bytes": SOURCE.stat().st_size,
            "http_range": [0, 16777215],
            "reported_full_object_bytes": 29208338602,
            "member": member_name,
            "member_declared_uncompressed_bytes": member_size,
            "stream_end": stream_end,
            "decoded_complete_rows": decoded_rows,
            "malformed_rows": malformed_rows,
            "named_identifiers_observed": len(available_ids),
            "empty_identifier_rows": counts.get("<empty>", 0),
            "first_named_identifier": next(item for item in identifier_order if item != "<empty>"),
            "last_identifier_reached": identifier_order[-1],
            "container_ids_path": str((OUT / "available_container_ids.txt").relative_to(ROOT)),
            "limitations": [
                "The 16 MiB HTTP-range prefix is not the complete approximately 29.2 GB object.",
                "Its SHA-256 cannot be compared with the official full-archive SHA-256.",
                "Identifiers and distributions in the prefix are not a random or representative sample.",
                "The final identifier reached may be truncated by the byte-range boundary.",
            ],
        },
        "schema": ["container_id", "machine_id", "time_stamp", "cpu_util_percent",
                   "mem_util_percent", "cpi", "mem_gps", "mpki", "net_in", "net_out",
                   "disk_io_percent"],
        "c_1": {
            "rows": len(c1_times),
            "unique_timestamps": len(set(c1_times)),
            "first_timestamp_seconds": min(c1_times),
            "last_timestamp_seconds": max(c1_times),
            "span_seconds": max(c1_times) - min(c1_times),
            "cpu_min": min(c1_cpu),
            "cpu_max": max(c1_cpu),
            "cpu_out_of_schema_range": sum(value < 0 or value > 100 for value in c1_cpu),
            "timestamp_nonmonotonic_in_stored_block": sum(right <= left for left, right in zip(times["c_1"], times["c_1"][1:])),
            "gap_statistics": describe_gaps(c1_times),
            "stored_block_complete_within_prefix": checks["c1_single_stored_block_before_c10"],
            "completeness_caveat": "The c_1 block ends before c_10 in the stored ordering, but completeness against the unavailable full archive cannot be independently proven.",
        },
        "selected_window": {
            "selection": "First 42 c_1 observations in timestamp order, committed before any Alibaba controller run.",
            "rows": len(replay),
            "first_timestamp_seconds": min(selected_times),
            "last_timestamp_seconds": max(selected_times),
            "source_span_seconds": max(selected_times) - min(selected_times),
            "unique_timestamps": len(set(selected_times)),
            "gap_statistics": describe_gaps(selected_times),
            "cpu_min": min(selected_cpu),
            "cpu_mean": statistics.mean(selected_cpu),
            "cpu_median": statistics.median(selected_cpu),
            "cpu_max": max(selected_cpu),
            "cpu_sample_sd": statistics.stdev(selected_cpu),
            "cpu_unique_values": len(set(selected_cpu)),
            "replay_trace_sha256": sha256(TRACE),
            "replay_duration_seconds": 420,
            "scheduled_measurement_requests": sum(round(rate * 10) for rate in target_rps),
            "mean_target_rps_from_schedule": sum(round(rate * 10) for rate in target_rps) / 420,
            "contiguous_at_10_second_cadence": describe_gaps(selected_times)["longest_10_second_cadence_run_observations"] == len(selected_times),
            "sufficiency_basis": "Exactly 42 genuine observations support a 42-bin observation-index replay without imputation or repetition. Source-time fidelity is explicitly discarded.",
        },
    }
    (OUT / "dataset_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"decision": report["decision"], "decoded_rows": decoded_rows,
                      "named_ids": len(available_ids), "c_1_rows": len(c1_times),
                      "selected_source_span_seconds": report["selected_window"]["source_span_seconds"],
                      "selected_longest_10s_run": report["selected_window"]["gap_statistics"]["longest_10_second_cadence_run_observations"]}, indent=2))
    if report["decision"] == "BLOCKED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
