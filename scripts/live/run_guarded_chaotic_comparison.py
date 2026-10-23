#!/usr/bin/env python3
"""Execute the frozen guarded chaotic matrix under cgroup and watchdog control."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/guarded_chaotic_comparison"
CONFIG = ROOT / "configs/guarded_chaotic_safety.json"
PROTOCOL = OUT / "affinity_revision_v2/SAFETY_PROTOCOL_V2.md"
K = [str(ROOT / ".tools/kubectl"), "--kubeconfig", str(ROOT / "live-kubeconfig"), "--request-timeout=15s"]


def now():
    return datetime.now(timezone.utc).isoformat()


def append(record):
    with (OUT / "execution_ledger.jsonl").open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def block_is_active(block):
    if not block.exists():
        return False
    resolution = OUT / "block_resolution.json"
    try:
        blocked = json.loads(block.read_text())
        resolved = json.loads(resolution.read_text())
        return resolved.get("resolved_blocked_utc") != blocked.get("blocked_utc")
    except (OSError, json.JSONDecodeError):
        return True


def main():
    smoke_gate = OUT / "affinity_revision_v2/smoke_gate.json"
    smoke = json.loads(smoke_gate.read_text()) if smoke_gate.exists() else {}
    if smoke.get("decision") != "PASS":
        raise RuntimeError("prospective v2 smoke gate did not pass")
    if smoke.get("protocol_sha256") != hashlib.sha256(PROTOCOL.read_bytes()).hexdigest():
        raise RuntimeError("safety protocol changed after the v2 smoke")
    if smoke.get("affinity_monitor_sha256") != hashlib.sha256(
            (ROOT / "scripts/live/guarded_exec.py").read_bytes()).hexdigest():
        raise RuntimeError("affinity monitor changed after the v2 smoke")
    plan = json.loads((OUT / "frozen_plan.json").read_text())
    preflight = json.loads((OUT / "resource_budget.json").read_text())
    if preflight.get("decision") != "PASS":
        raise RuntimeError("resource-isolation preflight did not pass")
    if plan["order"] != ["calibrated_hpa", "holtwinters", "strawman_hpa"]:
        raise RuntimeError("frozen balanced order changed")
    if hashlib.sha256((ROOT / plan["replay_path"]).read_bytes()).hexdigest() != plan["replay_sha256"]:
        raise RuntimeError("frozen replay changed")
    block = OUT / "BLOCK_NEW_RUNS"
    if block_is_active(block):
        raise RuntimeError(f"watchdog block is active: {block}")
    session = OUT / ("watchdog_session_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    session.mkdir(parents=True)
    runtime = session / "active_run.json"
    runtime.write_text(json.dumps({"active": False, "in_flight": 0, "updated_utc": now()}) + "\n")
    watchdog_command = [".venv/bin/python", "scripts/live/safety_watchdog.py", "--config",
                        str(CONFIG.relative_to(ROOT)), "--session-dir", str(session.relative_to(ROOT)),
                        "--runtime-state", str(runtime.relative_to(ROOT))]
    watchdog = subprocess.Popen(watchdog_command, cwd=ROOT, start_new_session=True)
    append({"event": "watchdog_started", "utc": now(), "pid": watchdog.pid,
            "session": str(session.relative_to(ROOT)), "command": watchdog_command})
    aborted = False
    try:
        for run in plan["runs"]:
            if block_is_active(block) or watchdog.poll() is not None:
                aborted = True
                raise RuntimeError("watchdog stopped or blocked the remaining matrix")
            run_dir = OUT / run["dataset"] / f"repeat{run['repeat']}" / run["arm"]
            if run_dir.exists():
                raise RuntimeError(f"refusing to overwrite evidence: {run_dir}")
            generator = [str(ROOT / ".venv/bin/python"), "scripts/live/run_trace.py",
                "--dataset", run["dataset"], "--arm", run["arm"], "--repeat", str(run["repeat"]),
                "--warmup", str(run["warmup"]), "--duration", str(run["duration"]),
                "--category", run["category"], "--max-inflight", str(run["max_inflight"]),
                "--runtime-state", str(runtime)]
            affinity_evidence = session / f"generator_enforcement_{run['sequence']}_{run['arm']}.json"
            command = ["systemd-run", "--user", "--scope", "--quiet",
                "-p", "AllowedCPUs=4-5", "-p", "CPUQuota=100%", "-p", "MemoryMax=768M",
                "-p", "MemorySwapMax=0", "-p", "TasksMax=512", "taskset", "--cpu-list", "4-5",
                str(ROOT / ".venv/bin/python"), "scripts/live/guarded_exec.py", "--evidence",
                str(affinity_evidence), "--expected-cpus", "4-5", "--"] + generator
            started = now()
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, start_new_session=True)
            append({"event": "collection", "sequence": run["sequence"], "run": run,
                    "started_utc": started, "finished_utc": now(), "returncode": process.returncode,
                    "stdout": process.stdout.replace(str(ROOT) + "/", ""),
                    "stderr": process.stderr.replace(str(ROOT) + "/", "")})
            enforcement = json.loads(affinity_evidence.read_text()) if affinity_evidence.exists() else {}
            enforcement_failed = enforcement.get("decision") != "PASS"
            if block_is_active(block) or (session / "safety_abort.json").exists() or process.returncode == 75 or enforcement_failed:
                aborted = True
                disposition = {"decision": "SAFETY_ABORTED", "arm": run["arm"],
                               "affinity_enforcement_failed": enforcement_failed,
                               "finished_utc": now(), "remaining_arms_not_run": [
                                   item["arm"] for item in plan["runs"] if item["sequence"] > run["sequence"]]}
                (OUT / "matrix_disposition.json").write_text(json.dumps(disposition, indent=2) + "\n")
                break
            if process.returncode:
                raise RuntimeError(f"collection failed for {run}; partial evidence retained")
            analysis_command = [str(ROOT / ".venv/bin/python"), "scripts/live/analyze_runs.py",
                                "--root", str(run_dir.relative_to(ROOT))]
            analysis = subprocess.run(analysis_command, cwd=ROOT, capture_output=True, text=True)
            append({"event": "analysis", "sequence": run["sequence"], "run": run,
                    "finished_utc": now(), "returncode": analysis.returncode,
                    "stdout": analysis.stdout.replace(str(ROOT) + "/", ""),
                    "stderr": analysis.stderr.replace(str(ROOT) + "/", "")})
            if analysis.returncode:
                raise RuntimeError(f"analysis failed for {run}")
            metadata = json.loads((run_dir / "metadata.json").read_text())
            if metadata.get("trace_sha256") != plan["replay_sha256"]:
                raise RuntimeError("arm used a non-frozen trace")
            print(f"{run['sequence']}/3 {run['arm']}: " +
                  json.loads((run_dir / "summary.json").read_text())["decision"], flush=True)
    finally:
        (session / "SESSION_COMPLETE").touch()
        try:
            watchdog.wait(timeout=15)
        except subprocess.TimeoutExpired:
            watchdog.terminate()
            watchdog.wait(timeout=5)
        cleanup = subprocess.run(K + ["-n", "trace-benchmark", "delete", "hpa,phpa", "--all",
                                   "--ignore-not-found=true"], capture_output=True, text=True)
        append({"event": "benchmark_controller_cleanup", "utc": now(),
                "returncode": cleanup.returncode, "stdout": cleanup.stdout, "stderr": cleanup.stderr})
    if aborted:
        raise SystemExit(75)


if __name__ == "__main__":
    main()
