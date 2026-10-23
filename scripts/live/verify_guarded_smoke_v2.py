#!/usr/bin/env python3
"""Independently recompute smoke attempt 4 and create the research gate."""

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
REVISION = OUT / "affinity_revision_v2"
RUN = OUT / "pilot_guarded_smoke/guarded_smoke/repeat4/calibrated_hpa"
SESSION = OUT / "smoke_watchdog_session_attempt4"
K = [str(ROOT / ".tools/kubectl"), "--kubeconfig", str(ROOT / "live-kubeconfig"),
     "--request-timeout=10s"]


def main():
    smoke = json.loads((OUT / "smoke_test_attempt4.json").read_text())
    protocol_record = json.loads((REVISION / "safety_protocol_v2.json").read_text())
    protocol_hash = hashlib.sha256((REVISION / "SAFETY_PROTOCOL_V2.md").read_bytes()).hexdigest()
    monitor_hash = hashlib.sha256((ROOT / protocol_record["affinity_monitor_path"]).read_bytes()).hexdigest()
    requests = list(csv.DictReader((RUN / "requests.csv").open()))
    measured = [row for row in requests if row["phase"] == "measurement"]
    successes = [row for row in measured if row["status"] == "200" and not row["error"]]
    enforcement = json.loads((SESSION / "generator_enforcement.json").read_text())
    telemetry = [json.loads(line) for line in (SESSION / "host_pressure.jsonl").read_text().splitlines()]
    policy = json.loads((ROOT / "configs/guarded_chaotic_safety.json").read_text())
    threshold = policy["thresholds"]
    controllers = subprocess.run(K + ["-n", "trace-benchmark", "get", "hpa,phpa", "-o", "json"],
                                 capture_output=True, text=True)
    try:
        controller_items = json.loads(controllers.stdout).get("items", [])
    except json.JSONDecodeError:
        controller_items = None
    processes = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True)
    active_generator = [line for line in processes.stdout.splitlines()
                        if "scripts/live/run_trace.py" in line]
    all_thread_records = [item for sample in enforcement["samples"] for item in sample["processes"]]
    checks = {
        "smoke_runner_reported_pass": smoke["decision"] == "PASS" and all(smoke["checks"].values()),
        "protocol_hash_frozen": smoke["protocol_sha256"] == protocol_hash,
        "affinity_monitor_hash_frozen": monitor_hash == protocol_record["affinity_monitor_sha256_at_freeze"],
        "complete_successful_measurement_schedule": len(measured) == len(successes) == 90,
        "metrics_complete_marker_present": (RUN / "COMPLETE").exists() and
            len((RUN / "metrics.jsonl").read_text().splitlines()) >= 6,
        "scheduler_wrapper_affinity": enforcement["wrapper_affinity"] == [4, 5],
        "scheduler_child_inheritance": enforcement["explicit_child_probe"]["allowed_cpus"] == [4, 5],
        "every_observed_thread_affinity": bool(all_thread_records) and
            all(item["allowed_cpus"] == [4, 5] for item in all_thread_records),
        "scope_limits": all(enforcement["cgroup_files"].get(key) == value for key, value in {
            "cpu.max": "100000 100000", "memory.max": "805306368",
            "memory.swap.max": "0", "pids.max": "512"}.items()),
        "watchdog_independent_and_complete": len(telemetry) >= 10 and
            (SESSION / "watchdog_complete.json").exists() and not (SESSION / "safety_abort.json").exists(),
        "host_thresholds_held": all(
            row["load1"] <= threshold["load1_max"] and
            row["cpu_utilization_percent"] <= threshold["cpu_utilization_percent_max"] and
            row["memory_available_bytes"] >= threshold["memory_available_bytes_min"] and
            row["swap_used_bytes"] <= threshold["swap_used_bytes_max"] and
            row["disk_free_bytes"] >= threshold["disk_free_bytes_min"] and
            row["memory_psi_full_avg10"] <= threshold["memory_psi_full_avg10_max"] and
            row["io_psi_full_avg10"] <= threshold["io_psi_full_avg10_max"] and
            row["cpu_psi_some_avg10"] <= threshold["cpu_psi_some_avg10_max"]
            for row in telemetry),
        "controllers_cleaned": controllers.returncode == 0 and controller_items == [],
        "no_generator_survived": not active_generator,
        "task12_failed_result_preserved": json.loads((OUT / "smoke_test_attempt3.json").read_text())["decision"] == "FAIL",
    }
    pressure = {"samples": len(telemetry), "max_load1": max(row["load1"] for row in telemetry),
                "max_cpu_utilization_percent": max(row["cpu_utilization_percent"] for row in telemetry),
                "min_memory_available_bytes": min(row["memory_available_bytes"] for row in telemetry),
                "max_swap_used_bytes": max(row["swap_used_bytes"] for row in telemetry),
                "max_cpu_psi_some_avg10": max(row["cpu_psi_some_avg10"] for row in telemetry),
                "max_memory_psi_full_avg10": max(row["memory_psi_full_avg10"] for row in telemetry),
                "max_io_psi_full_avg10": max(row["io_psi_full_avg10"] for row in telemetry),
                "min_disk_free_bytes": min(row["disk_free_bytes"] for row in telemetry)}
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "decision": "PASS" if all(checks.values()) else "FAIL",
              "protocol_sha256": protocol_hash, "affinity_monitor_sha256": monitor_hash,
              "checks": checks,
              "independent_counts": {"measurement": len(measured), "success": len(successes),
                                     "thread_observations": len(all_thread_records)},
              "host_pressure": pressure}
    (REVISION / "smoke_gate.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
