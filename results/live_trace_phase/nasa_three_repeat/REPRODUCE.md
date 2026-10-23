# Reproduce the NASA repetition milestone

From the repository root, with the existing `calibrated-live` cluster:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/live/run_nasa_repeats.py
.venv/bin/python scripts/live/analyze_runs.py --root results/live_trace_phase/nasa_three_repeat
.venv/bin/python scripts/live/verify_nasa_repeats.py
.venv/bin/python -m unittest discover -s tests -v
```

`run_nasa_repeats.py` writes the fixed plan before collection, executes arms
sequentially, refuses to overwrite existing evidence, checks free disk, records
subprocess results in `execution_ledger.jsonl`, and stops on any non-ACCEPT
analysis decision. It safely resumes by skipping only previously accepted runs.

The repeat-3 tuned-HPA arm produced two retained `INCONCLUSIVE` attempts due to
CPU telemetry below the fixed coverage threshold. Reproduction must not delete
or relabel those attempts. Any future completion attempt should be registered
as a new retained attempt and must not change workload or controller parameters.
