# Reproduce the first on/off comparison

Use the existing `calibrated-live` kind cluster and repository virtual environment:

```bash
.venv/bin/python scripts/live/prepare_onoff_comparison.py
.venv/bin/python scripts/live/preflight_onoff.py
.venv/bin/python scripts/live/run_onoff_comparison.py
.venv/bin/python scripts/live/verify_onoff_comparison.py
.venv/bin/python -m unittest discover -s tests -v
```

The runner refuses to overwrite unfinished or completed evidence. Delete nothing to resume: completed arms are skipped and an unfinished arm requires manual review. Raw request and Kubernetes telemetry are retained per arm.
