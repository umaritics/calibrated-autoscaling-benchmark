#!/usr/bin/env python3
"""Execute the frozen one-repeat, three-controller stepped comparison."""

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/stepped_first_comparison"
MIN_FREE_BYTES = 1024**3


def now():
    return datetime.now(timezone.utc).isoformat()


def append(record):
    with (OUT / "execution_ledger.jsonl").open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def portable(value):
    return value.replace(str(ROOT) + "/", "")


def main():
    plan = json.loads((OUT / "run_plan.json").read_text())
    frozen = json.loads((OUT / "frozen_plan.json").read_text())
    if [run["arm"] for run in plan] != ["calibrated_hpa", "holtwinters", "strawman_hpa"]:
        raise RuntimeError("frozen arm order changed")
    expected_hash = frozen["replay_sha256"]
    for run in plan:
        run_dir = OUT / run["dataset"] / f"repeat{run['repeat']}" / run["arm"]
        if (run_dir / "COMPLETE").exists():
            if not (run_dir / "summary.json").exists():
                raise RuntimeError(f"completed collection lacks analysis: {run_dir}")
            continue
        if run_dir.exists():
            raise RuntimeError(f"unfinished evidence requires review; refusing overwrite: {run_dir}")
        if shutil.disk_usage(ROOT).free < MIN_FREE_BYTES:
            raise RuntimeError("free disk below 1 GiB guard")
        command = [".venv/bin/python", "scripts/live/run_trace.py", "--dataset", run["dataset"],
                   "--arm", run["arm"], "--repeat", str(run["repeat"]),
                   "--warmup", str(run["warmup"]), "--duration", str(run["duration"]),
                   "--category", run["category"]]
        started = now()
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        append({"event": "collection", "sequence": run["sequence"], "run": run,
                "expected_trace_sha256": expected_hash, "command": command,
                "started_utc": started, "finished_utc": now(), "returncode": process.returncode,
                "stdout": portable(process.stdout), "stderr": portable(process.stderr)})
        if process.returncode:
            raise RuntimeError(f"collection failed for {run}; evidence retained")
        analysis_command = [".venv/bin/python", "scripts/live/analyze_runs.py", "--root",
                            str(run_dir.relative_to(ROOT))]
        analysis = subprocess.run(analysis_command, cwd=ROOT, capture_output=True, text=True)
        append({"event": "analysis", "sequence": run["sequence"], "run": run,
                "command": analysis_command, "finished_utc": now(), "returncode": analysis.returncode,
                "stdout": portable(analysis.stdout), "stderr": portable(analysis.stderr)})
        if analysis.returncode:
            raise RuntimeError(f"analysis failed for {run}; evidence retained")
        summary = json.loads((run_dir / "summary.json").read_text())
        metadata = json.loads((run_dir / "metadata.json").read_text())
        copied_hash = hashlib.sha256((run_dir / "trace.csv").read_bytes()).hexdigest()
        if metadata.get("trace_sha256") != expected_hash or copied_hash != expected_hash:
            raise RuntimeError("run used a non-frozen trace")
        print(f"{run['sequence']}/3 {run['arm']}: {summary['decision']}", flush=True)


if __name__ == "__main__":
    main()
