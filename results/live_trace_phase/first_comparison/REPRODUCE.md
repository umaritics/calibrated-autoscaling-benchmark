# Reproduction commands

Run from the repository root using the existing dedicated `calibrated-live` cluster. The frozen order is in `run_plan.json`.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/live/run_trace.py --dataset nasa --arm strawman_hpa --repeat 1 --warmup 120 --duration 420 --category first_comparison
.venv/bin/python scripts/live/analyze_runs.py --root results/live_trace_phase/first_comparison
.venv/bin/python scripts/live/run_trace.py --dataset nasa --arm calibrated_hpa --repeat 1 --warmup 120 --duration 420 --category first_comparison
.venv/bin/python scripts/live/analyze_runs.py --root results/live_trace_phase/first_comparison
.venv/bin/python scripts/live/run_trace.py --dataset nasa --arm holtwinters --repeat 1 --warmup 120 --duration 420 --category first_comparison
.venv/bin/python scripts/live/analyze_runs.py --root results/live_trace_phase/first_comparison
.venv/bin/python scripts/live/verify_first_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```
