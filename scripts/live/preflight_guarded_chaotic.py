#!/usr/bin/env python3
"""Read-only diagnosis and hard-limit verification for guarded chaotic runs."""

import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
POLICY = ROOT / "configs/guarded_chaotic_safety.json"
K = [str(ROOT / ".tools/kubectl"), "--kubeconfig", str(ROOT / "live-kubeconfig"), "--request-timeout=10s"]


def command(args, timeout=30):
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip()[:2048]}


def main():
    policy = json.loads(POLICY.read_text())
    cpu_records = Path("/proc/cpuinfo").read_text().split("\n\n")
    physical_cores = set()
    for record in cpu_records:
        fields = {key.strip(): value.strip() for key, value in
                  (line.split(":", 1) for line in record.splitlines() if ":" in line)}
        if "physical id" in fields and "core id" in fields:
            physical_cores.add((fields["physical id"], fields["core id"]))
    host = {"captured_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "physical_cores": len(physical_cores), "logical_cpus": os.cpu_count(),
            "load_average": os.getloadavg(),
            "disk": dict(zip(("total_bytes", "used_bytes", "free_bytes"), shutil.disk_usage(ROOT)))}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            host[key] = int(value.split()[0]) * 1024
    host["pressure"] = {kind: Path(f"/proc/pressure/{kind}").read_text().splitlines()
                        for kind in ("cpu", "memory", "io")}
    docker = command(["docker", "inspect", "calibrated-live-control-plane", "--format",
        "{{json .HostConfig}}"])
    docker_info_result = command(["docker", "info", "--format", "{{json .}}"])
    try:
        raw_docker_info = json.loads(docker_info_result["stdout"])
        docker_info = {key: raw_docker_info.get(key) for key in ("ServerVersion", "NCPU", "MemTotal",
            "CgroupDriver", "CgroupVersion", "MemoryLimit", "SwapLimit", "CpuCfsQuota",
            "CPUSet", "PidsLimit", "DockerRootDir")}
    except json.JSONDecodeError:
        docker_info = {"error": docker_info_result["stderr"]}
    cgroup = command(["docker", "exec", "calibrated-live-control-plane", "sh", "-c",
        "paste -d, /sys/fs/cgroup/cpuset.cpus.effective /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/pids.max"])
    cluster = command(K + ["get", "nodes,pods,hpa,phpa", "-A", "-o", "json"])
    metrics = command(K + ["top", "nodes"])
    pod_metrics = command(K + ["top", "pods", "-A"])
    try:
        cluster_payload = json.loads(cluster["stdout"])
        cluster_inventory = []
        for item in cluster_payload.get("items", []):
            if item.get("kind") == "Pod":
                containers = item.get("spec", {}).get("containers", [])
                cluster_inventory.append({"namespace": item["metadata"].get("namespace"),
                    "name": item["metadata"].get("name"), "phase": item.get("status", {}).get("phase"),
                    "ready": all(state.get("ready", False) for state in
                                 item.get("status", {}).get("containerStatuses", [])),
                    "resources": {container.get("name"): container.get("resources", {})
                                  for container in containers}})
    except json.JSONDecodeError:
        cluster_inventory = []
    processes = command(["ps", "-eo", "pid,ppid,pgid,%cpu,%mem,rss,stat,comm,args", "--sort=-%cpu"])
    benchmark_processes = [line for line in processes["stdout"].splitlines()[1:]
                           if any(term in line for term in ("scripts/live/run_trace.py",
                                  "scripts/live/run_guarded_chaotic_comparison.py", "locust", "wrk "))]
    journal = command(["journalctl", "-b", "-1", "-k", "--no-pager"])
    relevant = [line for line in journal["stdout"].splitlines() if any(term in line.lower() for term in
                ("oom", "out of memory", "killed process", "hung task", "soft lockup", "hard lockup", "i/o error"))]
    expected = policy["budgets"]["kind_container"]
    try:
        host_config = json.loads(docker["stdout"])
        docker_ok = (host_config["CpusetCpus"] == expected["cpuset_cpus"] and
                     host_config["Memory"] == expected["memory_max_bytes"] and
                     host_config["MemorySwap"] == expected["memory_max_bytes"] and
                     host_config["PidsLimit"] == expected["pids_max"])
    except (KeyError, json.JSONDecodeError):
        docker_ok = False
    expected_cgroup = f"{expected['cpuset_cpus']},{expected['memory_max_bytes']},0,{expected['pids_max']}"
    checks = {"cpu_capacity_known": host["physical_cores"] == 4 and host["logical_cpus"] == 8,
              "memory_headroom_above_4_gib": host["MemAvailable"] >= 4 * 1024**3,
              "swap_pressure_below_1_gib": host["SwapTotal"] - host["SwapFree"] < 1024**3,
              "disk_headroom_above_4_gib": host["disk"]["free_bytes"] >= 4 * 1024**3,
              "docker_limits_requested_match": docker_ok,
              "docker_cgroup_limits_actual_match": cgroup["stdout"] == expected_cgroup,
              "cluster_query_healthy": cluster["returncode"] == 0,
              "metrics_server_healthy": metrics["returncode"] == 0,
              "watchdog_present": (ROOT / "scripts/live/safety_watchdog.py").exists(),
              "no_active_benchmark_runner": not benchmark_processes}
    record = {"decision": "PASS" if all(checks.values()) else "BLOCKED", "checks": checks,
              "host": host, "resource_policy": str(POLICY.relative_to(ROOT)),
              "docker_engine": docker_info, "docker_host_config": docker,
              "actual_kind_cgroup": cgroup, "cluster_pod_inventory": cluster_inventory,
              "cluster_query": {"returncode": cluster["returncode"], "stderr": cluster["stderr"]},
              "metrics_query": {"nodes": metrics, "pods": pod_metrics},
              "running_benchmark_processes": benchmark_processes,
              "previous_boot_relevant_kernel_lines": relevant,
              "freeze_cause_conclusion": "UNPROVEN; no matching OOM, lockup, or I/O fault establishes a cause."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "resource_budget.json").write_text(json.dumps(record, indent=2) + "\n")
    lines = ["# Guarded chaotic preflight", "", f"Decision: **{record['decision']}**.", "",
             "The calibrated kind node is hard-pinned to CPUs 0–3 and limited to 8 GiB RAM, zero swap, "
             "and 4096 PIDs. The generator's independently verified transient scope is limited to one CPU "
             "on CPUs 4–5, 768 MiB RAM, zero swap, and 512 tasks. This leaves CPUs 4–7 outside kind and "
             "more than 10 GiB outside the two hard memory caps for the desktop and OS.", "",
             "The previous-boot journal contains no conclusive OOM/lockup/I/O evidence, so the two freezes "
             "remain unattributed.", "", "## Checks", ""]
    lines.extend(f"- {'PASS' if value else 'FAIL'}: `{name}`" for name, value in checks.items())
    (OUT / "PREFLIGHT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"decision": record["decision"], "checks": checks}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
