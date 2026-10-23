# Reproduce the first chaotic comparison

```bash
.venv/bin/python scripts/live/prepare_chaotic_comparison.py
.venv/bin/python scripts/live/preflight_chaotic.py
.venv/bin/python scripts/live/run_chaotic_comparison.py
.venv/bin/python scripts/live/verify_chaotic_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner uses the frozen soft HPA → Holt-Winters → tuned HPA order, skips completed arms, and refuses to overwrite unfinished evidence.
