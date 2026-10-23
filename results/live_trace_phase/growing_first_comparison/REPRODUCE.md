# Reproduce the first growing comparison

Use the existing `calibrated-live` kind cluster and repository environment:

```bash
.venv/bin/python scripts/live/prepare_growing_comparison.py
.venv/bin/python scripts/live/preflight_growing.py
.venv/bin/python scripts/live/run_growing_comparison.py
.venv/bin/python scripts/live/verify_growing_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

Preparation is deterministic. The runner skips completed arms and refuses to overwrite unfinished evidence. Review and preserve any unfinished directory separately before resuming.
