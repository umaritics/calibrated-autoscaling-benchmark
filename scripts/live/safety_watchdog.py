#!/usr/bin/env python3
"""Independent host-safety watchdog for guarded live benchmarks."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def meminfo():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            values[key] = int(value.split()[0]) * 1024
    return values


def psi(kind):
    result = {}
    for line in Path(f"/proc/pressure/{kind}").read_text().splitlines():
        fields = line.split()
        result[fields[0]] = {key: float(value) for key, value in
                             (field.split("=", 1) for field in fields[1:])}
    return result


def cpu_counters():
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = [int(value) for value in fields]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def cpu_percent(previous, current):
    if previous is None:
        return 0.0
    total = current[0] - previous[0]
    idle = current[1] - previous[1]
    return 0.0 if total <= 0 else 100.0 * (total - idle) / total


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def workload_health(kubectl):
    command = kubectl + ["-n", "trace-benchmark", "get", "deploy", "php-apache", "-o", "json"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5)
        if completed.returncode:
            return {"query_ok": False, "ready_replicas": 0,
                    "error": completed.stderr.strip()[:512]}
        deployment = json.loads(completed.stdout)
        return {"query_ok": True,
                "ready_replicas": int(deployment.get("status", {}).get("readyReplicas", 0)),
                "available_replicas": int(deployment.get("status", {}).get("availableReplicas", 0)),
                "replicas": int(deployment.get("status", {}).get("replicas", 0))}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return {"query_ok": False, "ready_replicas": 0, "error": str(error)[:512]}


def snapshot(root, previous_cpu, runtime, kubectl, check_workload=True):
    current_cpu = cpu_counters()
    memory = meminfo()
    disk = shutil.disk_usage(root)
    record = {
        "utc": utc_now(), "monotonic_seconds": time.monotonic(),
        "load1": os.getloadavg()[0],
        "cpu_utilization_percent": cpu_percent(previous_cpu, current_cpu),
        "memory_available_bytes": memory["MemAvailable"],
        "swap_used_bytes": memory["SwapTotal"] - memory["SwapFree"],
        "disk_free_bytes": disk.free,
        "cpu_psi_some_avg10": psi("cpu")["some"]["avg10"],
        "memory_psi_full_avg10": psi("memory")["full"]["avg10"],
        "io_psi_full_avg10": psi("io")["full"]["avg10"],
        "generator_in_flight": int(runtime.get("in_flight", 0)),
        "generator_active": bool(runtime.get("active", False)),
    }
    if check_workload:
        record["workload"] = workload_health(kubectl)
    return current_cpu, record


def violations(record, thresholds):
    checks = {
        "load1_high": record["load1"] > thresholds["load1_max"],
        "cpu_utilization_high": record["cpu_utilization_percent"] > thresholds["cpu_utilization_percent_max"],
        "memory_available_low": record["memory_available_bytes"] < thresholds["memory_available_bytes_min"],
        "memory_pressure_high": record["memory_psi_full_avg10"] > thresholds["memory_psi_full_avg10_max"],
        "io_pressure_high": record["io_psi_full_avg10"] > thresholds["io_psi_full_avg10_max"],
        "cpu_pressure_high": record["cpu_psi_some_avg10"] > thresholds["cpu_psi_some_avg10_max"],
        "swap_usage_high": record["swap_used_bytes"] > thresholds["swap_used_bytes_max"],
        "disk_free_low": record["disk_free_bytes"] < thresholds["disk_free_bytes_min"],
        "generator_in_flight_high": record["generator_in_flight"] > thresholds["generator_in_flight_max"],
    }
    if record.get("generator_active") and "workload" in record:
        checks["workload_unhealthy"] = (
            not record["workload"].get("query_ok") or
            record["workload"].get("ready_replicas", 0) < thresholds["workload_ready_replicas_min"])
    return [name for name, failed in checks.items() if failed]


def terminate_target(runtime, graceful_seconds):
    result = {"attempted": False, "term_sent": False, "forced": False}
    pid = int(runtime.get("pid", 0) or 0)
    pgid = int(runtime.get("pgid", 0) or 0)
    if pid <= 1:
        return result
    result.update(attempted=True, pid=pid, pgid=pgid)
    try:
        if pgid > 1 and pgid != os.getpgrp():
            os.killpg(pgid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        result["term_sent"] = True
    except ProcessLookupError:
        result["already_exited"] = True
        return result
    deadline = time.monotonic() + graceful_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
            stat = Path(f"/proc/{pid}/stat").read_text().split()
            if len(stat) > 2 and stat[2] == "Z":
                result["clean_exit"] = True
                return result
        except ProcessLookupError:
            result["clean_exit"] = True
            return result
        except OSError:
            pass
        time.sleep(.1)
    try:
        if pgid > 1 and pgid != os.getpgrp():
            os.killpg(pgid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
        result["forced"] = True
    except ProcessLookupError:
        result["clean_exit"] = True
    return result


def run(args):
    config = read_json(args.config)
    thresholds = config["thresholds"]
    session = Path(args.session_dir)
    session.mkdir(parents=True, exist_ok=True)
    telemetry = session / "host_pressure.jsonl"
    block = session.parent / "BLOCK_NEW_RUNS"
    abort_path = session / "safety_abort.json"
    counts = {}
    previous_cpu = None
    sample_number = 0
    with telemetry.open("a", buffering=1) as log:
        while not (session / "SESSION_COMPLETE").exists():
            runtime = read_json(args.runtime_state)
            previous_cpu, record = snapshot(args.root, previous_cpu, runtime, args.kubectl, True)
            current = violations(record, thresholds)
            for name in set(counts) | set(current):
                counts[name] = counts.get(name, 0) + 1 if name in current else 0
            record["violations"] = current
            record["consecutive_counts"] = counts.copy()
            log.write(json.dumps(record, sort_keys=True) + "\n")
            sustained = sorted(name for name, count in counts.items()
                               if count >= config["sustained_samples"])
            if sustained:
                action = terminate_target(runtime, config["graceful_stop_seconds"])
                abort = {"decision": "SAFETY_ABORTED", "detected_utc": utc_now(),
                         "reasons": sustained, "sample": record, "termination": action,
                         "runtime_state": runtime}
                atomic_json(abort_path, abort)
                block.write_text(json.dumps({"blocked_utc": utc_now(), "reasons": sustained}) + "\n")
                return 75
            sample_number += 1
            time.sleep(config["sample_interval_seconds"])
    atomic_json(session / "watchdog_complete.json",
                {"decision": "PASS", "finished_utc": utc_now(), "samples": sample_number})
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--runtime-state", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--kubectl", nargs="+", default=[str(ROOT / ".tools/kubectl"),
                        "--kubeconfig", str(ROOT / "live-kubeconfig"), "--request-timeout=5s"])
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
