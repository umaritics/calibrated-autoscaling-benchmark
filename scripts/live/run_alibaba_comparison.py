#!/usr/bin/env python3
"""Execute the frozen one-repeat, three-controller Alibaba-derived comparison."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/live_trace_phase/alibaba_first_comparison"
PLAN_PATH = OUT / "run_plan.json"
MIN_FREE_BYTES = 1024**3


def now():
    return datetime.now(timezone.utc).isoformat()


def append(record):
    with (OUT / "execution_ledger.jsonl").open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main():
    plan = json.loads(PLAN_PATH.read_text())
    frozen = json.loads((OUT / "dataset_validation.json").read_text())
    if frozen["decision"] != "PASS_WITH_SEVERE_LIMITATIONS":
        raise RuntimeError("dataset validation did not pass")
    if frozen["selected_window"]["replay_trace_sha256"] != "5bc5d7705562b791602824bc8498866cef92db0a726b48c7c9aeeecccb850e47":
        raise RuntimeError("frozen replay hash changed")

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
                "command": command, "started_utc": started, "finished_utc": now(),
                "returncode": process.returncode, "stdout": process.stdout,
                "stderr": process.stderr})
        if process.returncode:
            raise RuntimeError(f"collection failed for {run}; evidence retained")

        analysis_command = [".venv/bin/python", "scripts/live/analyze_runs.py", "--root",
                            str(run_dir.relative_to(ROOT))]
        analysis = subprocess.run(analysis_command, cwd=ROOT, capture_output=True, text=True)
        append({"event": "analysis", "sequence": run["sequence"], "run": run,
                "command": analysis_command, "finished_utc": now(),
                "returncode": analysis.returncode, "stdout": analysis.stdout,
                "stderr": analysis.stderr})
        if analysis.returncode:
            raise RuntimeError(f"analysis failed for {run}; evidence retained")
        decision = json.loads((run_dir / "summary.json").read_text())["decision"]
        print(f"{run['sequence']}/3 {run['arm']}: {decision}", flush=True)


if __name__ == "__main__":
    main()
