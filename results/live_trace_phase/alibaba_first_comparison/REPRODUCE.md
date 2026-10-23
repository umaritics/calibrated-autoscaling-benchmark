# Reproduce the first Alibaba-derived comparison

With the retained source prefix and existing `calibrated-live` cluster:

```bash
.venv/bin/python scripts/live/validate_alibaba_subset.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/live/preflight_alibaba.py
.venv/bin/python scripts/live/run_alibaba_comparison.py
.venv/bin/python scripts/live/verify_alibaba_comparison.py
```

The runner executes the frozen order in `run_plan.json`, refuses to overwrite
any run directory, and stops after any instrumentation-invalid result. One
replacement is permitted only for a specifically diagnosed instrumentation
failure and must use the same frozen workload and controller settings.
