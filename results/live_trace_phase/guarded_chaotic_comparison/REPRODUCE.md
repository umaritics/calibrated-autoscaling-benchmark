# Reproduce the guarded chaotic comparison

```bash
.venv/bin/python scripts/live/prepare_guarded_chaotic_comparison.py
.venv/bin/python scripts/live/diagnose_affinity_gate.py
.venv/bin/python scripts/live/preflight_guarded_chaotic.py
.venv/bin/python scripts/live/validate_guarded_safety_v2.py
.venv/bin/python scripts/live/run_guarded_smoke.py
.venv/bin/python scripts/live/verify_guarded_smoke_v2.py
.venv/bin/python scripts/live/run_guarded_chaotic_comparison.py
.venv/bin/python scripts/live/verify_guarded_chaotic_comparison.py
```

The committed matrix is complete and runners refuse to overwrite it. These
commands describe a fresh checkout/new evidence destination; do not rerun an
accepted arm to improve or replace its outcome. Protocol v2 must already be
frozen before the smoke, and research execution requires the matching smoke
gate hash.
