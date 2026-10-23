#!/usr/bin/env python3
"""Run the six remaining NASA arms in the predeclared balanced order."""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/nasa_three_repeat"
RUNS = [
    {"sequence": 4, "dataset": "nasa", "arm": "calibrated_hpa", "repeat": 2},
    {"sequence": 5, "dataset": "nasa", "arm": "holtwinters", "repeat": 2},
    {"sequence": 6, "dataset": "nasa", "arm": "strawman_hpa", "repeat": 2},
    {"sequence": 7, "dataset": "nasa", "arm": "holtwinters", "repeat": 3},
    {"sequence": 8, "dataset": "nasa", "arm": "strawman_hpa", "repeat": 3},
    {"sequence": 9, "dataset": "nasa", "arm": "calibrated_hpa", "repeat": 3},
]
MIN_FREE_BYTES = 1024**3


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path, record):
    with path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = [run | {"warmup": 120, "duration": 420, "category": "nasa_three_repeat"} for run in RUNS]
    plan_path = OUT / "run_plan.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != plan:
            raise RuntimeError(f"frozen plan differs from {plan_path}")
    else:
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    ledger = OUT / "execution_ledger.jsonl"
    checkpoint = OUT / "checkpoint.json"
    for run in plan:
        run_dir = OUT / "nasa" / f"repeat{run['repeat']}" / run["arm"]
        if (run_dir / "COMPLETE").exists():
            summary_path = run_dir / "summary.json"
            if not summary_path.exists():
                raise RuntimeError(f"completed run lacks analysis: {run_dir}")
            decision = json.loads(summary_path.read_text()).get("decision")
            if decision != "ACCEPT":
                raise RuntimeError(f"completed run is {decision}, not ACCEPT: {run_dir}")
            continue
        if run_dir.exists():
            raise RuntimeError(f"unfinished evidence requires review; refusing overwrite: {run_dir}")

        free_bytes = shutil.disk_usage(ROOT).free
        if free_bytes < MIN_FREE_BYTES:
            raise RuntimeError(f"free disk below 1 GiB guard: {free_bytes} bytes")
        checkpoint.write_text(json.dumps({"state": "running", "run": run, "started_utc": utc_now(),
                                          "free_disk_bytes": free_bytes}, indent=2) + "\n")
        command = [sys.executable, "scripts/live/run_trace.py",
                   "--dataset", "nasa", "--arm", run["arm"], "--repeat", str(run["repeat"]),
                   "--warmup", "120", "--duration", "420", "--category", "nasa_three_repeat"]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        append_jsonl(ledger, {"event": "collection", "run": run, "command": command,
                              "returncode": process.returncode, "stdout": process.stdout,
                              "stderr": process.stderr, "finished_utc": utc_now()})
        if process.returncode:
            checkpoint.write_text(json.dumps({"state": "collection_failed", "run": run,
                                              "returncode": process.returncode,
                                              "finished_utc": utc_now()}, indent=2) + "\n")
            raise RuntimeError(f"collection failed for {run}; inspect {ledger}")

        analysis_command = [sys.executable, "scripts/live/analyze_runs.py",
                            "--root", str(OUT.relative_to(ROOT))]
        analysis = subprocess.run(analysis_command, cwd=ROOT, capture_output=True, text=True)
        append_jsonl(ledger, {"event": "analysis", "run": run, "command": analysis_command,
                              "returncode": analysis.returncode, "stdout": analysis.stdout,
                              "stderr": analysis.stderr, "finished_utc": utc_now()})
        if analysis.returncode:
            checkpoint.write_text(json.dumps({"state": "analysis_failed", "run": run,
                                              "returncode": analysis.returncode,
                                              "finished_utc": utc_now()}, indent=2) + "\n")
            raise RuntimeError(f"analysis failed for {run}; inspect {ledger}")
        summary = json.loads((run_dir / "summary.json").read_text())
        if summary.get("decision") != "ACCEPT":
            checkpoint.write_text(json.dumps({"state": "integrity_stop", "run": run,
                                              "decision": summary.get("decision"),
                                              "failed_checks": [key for key, value in summary["checks"].items() if not value],
                                              "finished_utc": utc_now()}, indent=2) + "\n")
            raise RuntimeError(f"integrity decision {summary.get('decision')} for {run}; stopping")
        checkpoint.write_text(json.dumps({"state": "accepted", "last_run": run,
                                          "decision": "ACCEPT", "finished_utc": utc_now(),
                                          "free_disk_bytes": shutil.disk_usage(ROOT).free}, indent=2) + "\n")
        print(f"ACCEPT sequence {run['sequence']}: repeat {run['repeat']} {run['arm']}", flush=True)

    checkpoint.write_text(json.dumps({"state": "complete", "accepted_runs": len(plan),
                                      "finished_utc": utc_now(),
                                      "free_disk_bytes": shutil.disk_usage(ROOT).free}, indent=2) + "\n")


if __name__ == "__main__":
    main()
