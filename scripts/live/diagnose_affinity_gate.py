#!/usr/bin/env python3
"""Capture the host/cgroup facts that motivated safety protocol v2."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from guarded_exec import cgroup_path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison/affinity_revision_v2"


def run(args):
    completed = subprocess.run(args, capture_output=True, text=True)
    return {"command": args, "returncode": completed.returncode,
            "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def main():
    unified = Path("/sys/fs/cgroup")
    user_cgroup = cgroup_path(os.getpid())
    parent = unified / user_cgroup.lstrip("/")
    record = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "conclusion": "Task 12 read the correct live scope; cpuset.cpus.effective was absent because the cpuset controller was not instantiated in that user scope. AllowedCPUs alone therefore lacked the required read-back proof.",
        "current_process_cgroup": user_cgroup,
        "unified_mount": run(["findmnt", "-no", "FSTYPE,OPTIONS", "/sys/fs/cgroup"]),
        "root_controllers": (unified / "cgroup.controllers").read_text().strip(),
        "root_subtree_control": (unified / "cgroup.subtree_control").read_text().strip(),
        "current_parent_controllers": (parent / "cgroup.controllers").read_text().strip() if (parent / "cgroup.controllers").exists() else None,
        "current_parent_subtree_control": (parent / "cgroup.subtree_control").read_text().strip() if (parent / "cgroup.subtree_control").exists() else None,
        "cpu_topology": run(["lscpu", "-e=CPU,CORE,SOCKET,NODE,ONLINE"]),
        "online_cpus": Path("/sys/devices/system/cpu/online").read_text().strip(),
        "task12_scope_evidence": json.loads((OUT.parent / "smoke_test_attempt3.json").read_text()),
        "kind_host_config": run(["docker", "inspect", "calibrated-live-control-plane", "--format", "{{json .HostConfig}}"]),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cpu_affinity_diagnosis.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"output": str((OUT / 'cpu_affinity_diagnosis.json').relative_to(ROOT)),
                      "online_cpus": record["online_cpus"]}, indent=2))


if __name__ == "__main__":
    main()
