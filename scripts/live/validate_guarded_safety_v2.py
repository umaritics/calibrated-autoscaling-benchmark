#!/usr/bin/env python3
"""Run and preserve the pre-smoke safety validation suite."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
REVISION = OUT / "affinity_revision_v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    command = [sys.executable, "-m", "unittest", "tests.test_guarded_exec",
               "tests.test_safety_watchdog", "tests.test_guarded_matrix_gate", "-v"]
    tests = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    protocol = json.loads((REVISION / "safety_protocol_v2.json").read_text())
    task12 = json.loads((OUT / "smoke_test_attempt3.json").read_text())
    probe = json.loads((REVISION / "kernel_probe.json").read_text())
    resource = json.loads((OUT / "resource_budget.json").read_text())
    checks = {
        "focused_tests_pass": tests.returncode == 0,
        "protocol_hash_matches": sha(REVISION / "SAFETY_PROTOCOL_V2.md") == protocol["protocol_sha256"],
        "affinity_monitor_hash_matches_freeze": sha(ROOT / protocol["affinity_monitor_path"]) ==
            protocol["affinity_monitor_sha256_at_freeze"],
        "resource_policy_hash_matches_freeze": sha(ROOT / protocol["resource_policy_path"]) ==
            protocol["resource_policy_sha256"],
        "old_smoke_remains_failed": task12["decision"] == "FAIL",
        "scheduler_affinity_probe_passed": probe["decision"] == "PASS" and not probe["violations"],
        "all_probe_threads_restricted": probe["observed_thread_records"] > 0 and all(
            item["allowed_cpus"] == [4, 5]
            for sample in probe["samples"] for item in sample["processes"]),
        "probe_child_inherited_affinity": probe["explicit_child_probe"]["allowed_cpus"] == [4, 5],
        "quota_memory_swap_pid_limits": all(probe["cgroup_files"].get(key) == value for key, value in {
            "cpu.max": "100000 100000", "memory.max": "805306368",
            "memory.swap.max": "0", "pids.max": "512"}.items()),
        "cpuset_absence_recorded_not_fabricated": isinstance(
            probe["cgroup_files"].get("cpuset.cpus.effective"), dict),
        "kind_limits_and_cluster_preflight_pass": resource["decision"] == "PASS" and
            resource["checks"]["docker_cgroup_limits_actual_match"],
    }
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "decision": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "test_command": [".venv/bin/python", "-m", "unittest",
                               "tests.test_guarded_exec", "tests.test_safety_watchdog",
                               "tests.test_guarded_matrix_gate", "-v"],
              "tests_returncode": tests.returncode, "tests_stdout": tests.stdout,
              "tests_stderr": tests.stderr}
    (REVISION / "pre_smoke_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "checks": checks}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
