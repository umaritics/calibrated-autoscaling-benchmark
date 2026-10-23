# Reproduce the first stepped comparison

```bash
.venv/bin/python scripts/live/prepare_stepped_comparison.py
.venv/bin/python scripts/live/preflight_stepped.py
.venv/bin/python scripts/live/run_stepped_comparison.py
.venv/bin/python scripts/live/verify_stepped_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner uses the frozen tuned → Holt-Winters → soft order, skips complete arms, and refuses to overwrite unfinished evidence.
