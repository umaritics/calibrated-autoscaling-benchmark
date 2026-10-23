#!/usr/bin/env python3
"""Run one command while independently auditing scheduler and cgroup limits."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


CGROUP_FILES = ("cpuset.cpus.effective", "cpu.max", "memory.max", "memory.swap.max", "pids.max")


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def parse_cpu_list(value):
    cpus = set()
    for part in value.strip().split(","):
        if not part:
            continue
        bounds = part.split("-", 1)
        start = int(bounds[0])
        stop = int(bounds[-1])
        cpus.update(range(start, stop + 1))
    return cpus


def cgroup_path(pid):
    for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines():
        hierarchy, controllers, path = line.split(":", 2)
        if hierarchy == "0" and not controllers:
            return path
    raise RuntimeError(f"PID {pid} has no unified cgroup entry")


def cgroup_values(pid):
    relative = cgroup_path(pid)
    base = Path("/sys/fs/cgroup") / relative.lstrip("/")
    values = {}
    for name in CGROUP_FILES:
        try:
            values[name] = (base / name).read_text().strip()
        except OSError as exc:
            values[name] = {"unavailable": type(exc).__name__, "errno": exc.errno}
    return relative, values


def proc_table():
    table = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().split()
            table[int(entry.name)] = int(fields[3])
        except (OSError, ValueError, IndexError):
            continue
    return table


def descendants(root_pid):
    table = proc_table()
    found = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, ppid in table.items():
            if ppid in found and pid not in found:
                found.add(pid)
                changed = True
    return sorted(found)


def affinity_snapshot(root_pid):
    records = []
    for pid in descendants(root_pid):
        task_dir = Path(f"/proc/{pid}/task")
        try:
            tids = sorted(int(item.name) for item in task_dir.iterdir() if item.name.isdigit())
        except OSError:
            continue
        for tid in tids:
            try:
                allowed = sorted(os.sched_getaffinity(tid))
                status = Path(f"/proc/{pid}/task/{tid}/status").read_text()
                status_allowed = next(line.split(":", 1)[1].strip() for line in status.splitlines()
                                      if line.startswith("Cpus_allowed_list:"))
                records.append({"pid": pid, "tid": tid, "allowed_cpus": allowed,
                                "proc_status_cpus_allowed_list": status_allowed})
            except (OSError, StopIteration):
                continue
    return records


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def systemd_properties(relative_cgroup):
    unit = Path(relative_cgroup).name
    if not unit.endswith(".scope"):
        return {"unit": unit, "error": "cgroup is not a transient scope"}
    completed = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=AllowedCPUs,EffectiveCPUs,CPUQuotaPerSecUSec,MemoryMax,MemorySwapMax,TasksMax"],
        capture_output=True, text=True, timeout=10)
    return {"unit": unit, "returncode": completed.returncode,
            "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-cpus", default="4-5")
    parser.add_argument("--sample-seconds", type=float, default=0.1)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    expected = parse_cpu_list(args.expected_cpus)
    wrapper_affinity = sorted(os.sched_getaffinity(0))
    relative, limits = cgroup_values(os.getpid())
    child_probe = subprocess.run(
        [sys.executable, "-c", "import json,os;print(json.dumps(sorted(os.sched_getaffinity(0))))"],
        capture_output=True, text=True, timeout=10)
    try:
        child_affinity = json.loads(child_probe.stdout)
    except json.JSONDecodeError:
        child_affinity = None
    record = {
        "schema_version": 1, "started_utc": utcnow(), "expected_cpus": sorted(expected),
        "enforcement": "Linux scheduler affinity via taskset/sched_setaffinity",
        "wrapper_pid": os.getpid(), "wrapper_affinity": wrapper_affinity,
        "explicit_child_probe": {"returncode": child_probe.returncode,
                                 "allowed_cpus": child_affinity,
                                 "stderr": child_probe.stderr.strip()},
        "cgroup": relative, "cgroup_files": limits,
        "systemd_scope": systemd_properties(relative), "samples": [], "violations": []}
    if set(wrapper_affinity) != expected:
        record["violations"].append("wrapper_affinity_mismatch")
    if set(child_affinity or []) != expected:
        record["violations"].append("child_inheritance_mismatch")
    expected_limits = {"cpu.max": "100000 100000", "memory.max": "805306368",
                       "memory.swap.max": "0", "pids.max": "512"}
    for name, value in expected_limits.items():
        if limits.get(name) != value:
            record["violations"].append(f"{name}_mismatch")
    write_json(args.evidence, record)

    child = subprocess.Popen(command)
    stop_requested = False

    def stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        if child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while child.poll() is None:
        sample = {"utc": utcnow(), "processes": affinity_snapshot(child.pid)}
        record["samples"].append(sample)
        for item in sample["processes"]:
            if set(item["allowed_cpus"]) != expected:
                record["violations"].append(
                    f"affinity_mismatch_pid_{item['pid']}_tid_{item['tid']}")
        if record["violations"] and child.poll() is None:
            child.terminate()
        write_json(args.evidence, record)
        time.sleep(args.sample_seconds)
    returncode = child.wait()
    record.update(finished_utc=utcnow(), command_returncode=returncode,
                  observed_samples=len(record["samples"]),
                  observed_thread_records=sum(len(item["processes"]) for item in record["samples"]),
                  decision="PASS" if not record["violations"] else "FAIL",
                  stop_requested=stop_requested)
    write_json(args.evidence, record)
    if record["violations"]:
        return 78
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
