#!/usr/bin/env python3
"""Low-intensity infrastructure smoke test; never interpreted as controller evidence."""

import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
CONFIG = ROOT / "configs/guarded_chaotic_safety.json"
PROTOCOL = OUT / "affinity_revision_v2/SAFETY_PROTOCOL_V2.md"
K = [str(ROOT / ".tools/kubectl"), "--kubeconfig", str(ROOT / "live-kubeconfig"), "--request-timeout=10s"]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def block_is_active():
    block = OUT / "BLOCK_NEW_RUNS"
    if not block.exists():
        return False
    blocked = read_json(block)
    resolved = read_json(OUT / "block_resolution.json")
    return resolved.get("resolved_blocked_utc") != blocked.get("blocked_utc")


def main():
    if not PROTOCOL.exists():
        raise RuntimeError("prospective safety protocol v2 must exist before smoke launch")
    if block_is_active():
        raise RuntimeError("unresolved watchdog block prevents smoke launch")
    attempt = 1
    while (OUT / f"pilot_guarded_smoke/guarded_smoke/repeat{attempt}/calibrated_hpa").exists():
        attempt += 1
    run = OUT / f"pilot_guarded_smoke/guarded_smoke/repeat{attempt}/calibrated_hpa"
    session = OUT / f"smoke_watchdog_session_attempt{attempt}"
    runtime_path = session / "active_run.json"
    session.mkdir(parents=True)
    affinity_evidence = session / "generator_enforcement.json"
    runtime_path.write_text(json.dumps({"active": False, "in_flight": 0}) + "\n")
    watchdog = subprocess.Popen([sys.executable, "scripts/live/safety_watchdog.py", "--config", str(CONFIG),
        "--session-dir", str(session), "--runtime-state", str(runtime_path)], cwd=ROOT, start_new_session=True)
    generator = [str(ROOT / ".venv/bin/python"), "scripts/live/run_trace.py", "--dataset", "guarded_smoke",
        "--arm", "calibrated_hpa", "--repeat", str(attempt), "--warmup", "10", "--duration", "30",
        "--category", "guarded_chaotic_comparison/pilot_guarded_smoke", "--max-inflight", "32",
        "--runtime-state", str(runtime_path)]
    command = ["systemd-run", "--user", "--scope", "--quiet", "-p", "AllowedCPUs=4-5",
        "-p", "CPUQuota=100%", "-p", "MemoryMax=768M", "-p", "MemorySwapMax=0",
        "-p", "TasksMax=512", "taskset", "--cpu-list", "4-5", str(ROOT / ".venv/bin/python"),
        "scripts/live/guarded_exec.py", "--evidence", str(affinity_evidence),
        "--expected-cpus", "4-5", "--"] + generator
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    cgroup_values = {}
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        runtime = read_json(runtime_path)
        if runtime.get("active") and runtime.get("cgroup"):
            base = Path("/sys/fs/cgroup") / runtime["cgroup"].lstrip("/")
            for name in ("cpuset.cpus.effective", "cpu.max", "memory.max", "memory.swap.max", "pids.max"):
                try:
                    cgroup_values[name] = (base / name).read_text().strip()
                except OSError:
                    pass
            if len(cgroup_values) == 5:
                break
        if process.poll() is not None:
            break
        time.sleep(.2)
    stdout, stderr = process.communicate()
    (session / "SESSION_COMPLETE").touch()
    try:
        watchdog.wait(timeout=15)
    except subprocess.TimeoutExpired:
        watchdog.terminate();watchdog.wait(timeout=5)
    subprocess.run(K + ["-n", "trace-benchmark", "delete", "hpa,phpa", "--all",
                    "--ignore-not-found=true"], capture_output=True, text=True)
    requests = list(csv.DictReader((run / "requests.csv").open())) if (run / "requests.csv").exists() else []
    measurement = [row for row in requests if row["phase"] == "measurement"]
    successes = [row for row in measurement if row["status"] == "200" and not row["error"]]
    telemetry = [json.loads(line) for line in (session / "host_pressure.jsonl").read_text().splitlines()]
    metrics = (run / "metrics.jsonl").read_text().splitlines() if (run / "metrics.jsonl").exists() else []
    enforcement = read_json(affinity_evidence)
    expected_limits = {"cpu.max": "100000 100000", "memory.max": "805306368",
                       "memory.swap.max": "0", "pids.max": "512"}
    scope_limits = enforcement.get("cgroup_files", {})
    checks = {"generator_completed": process.returncode == 0 and (run / "COMPLETE").exists(),
              "actual_requests_reached_service": len(successes) > 0,
              "all_measurement_requests_recorded": len(measurement) == 90,
              "metrics_collected": len(metrics) >= 6,
              "watchdog_collected_host_pressure": len(telemetry) >= 10,
              "watchdog_did_not_abort": not (session / "safety_abort.json").exists(),
              "generator_scheduler_affinity_actual_match": enforcement.get("decision") == "PASS" and
                  enforcement.get("wrapper_affinity") == [4, 5] and
                  enforcement.get("explicit_child_probe", {}).get("allowed_cpus") == [4, 5] and
                  enforcement.get("observed_thread_records", 0) > 0,
              "generator_cgroup_limits_actual_match": all(scope_limits.get(name) == value
                                                            for name, value in expected_limits.items()),
              "dispatch_timing_healthy": bool(measurement) and
                  max(float(row["dispatch_s"]) - float(row["planned_s"])
                      for row in measurement) < .1,
              "host_memory_stayed_above_threshold": min(row["memory_available_bytes"] for row in telemetry) >= 4 * 1024**3,
              "disk_stayed_above_threshold": min(row["disk_free_bytes"] for row in telemetry) >= 4 * 1024**3}
    result = {"scope": "infrastructure smoke only; not controller research evidence",
              "attempt": attempt, "started_or_finished_utc": now(), "decision": "PASS" if all(checks.values()) else "FAIL",
              "checks": checks, "successful_measurement_requests": len(successes),
              "measurement_records": len(measurement), "watchdog_samples": len(telemetry),
              "actual_generator_cgroup": cgroup_values,
              "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
              "kernel_affinity_evidence": str(affinity_evidence.relative_to(ROOT)),
              "stdout": stdout.replace(str(ROOT) + "/", ""),
              "stderr": stderr.replace(str(ROOT) + "/", "")}
    (OUT / f"smoke_test_attempt{attempt}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not all(checks.values()):
        (OUT / "SAFETY_GATE_BLOCK.json").write_text(json.dumps({
            "blocked_utc": now(), "reason": "SMOKE_V2_SAFETY_GATE_FAILED",
            "failed_checks": [name for name, passed in checks.items() if not passed],
            "effect": "The research orchestrator must not launch any guarded chaotic controller arm.",
            "research_arms_started": False}, indent=2) + "\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
