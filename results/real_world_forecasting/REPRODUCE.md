# Reproduce the real-world forecasting milestone

No Kubernetes or Docker workload is required.

```bash
.venv/bin/python -m unittest tests.test_real_world_forecasting -v
.venv/bin/python scripts/real_world_forecasting.py
.venv/bin/python scripts/verify_real_world_forecasting.py
```

The evaluator streams both compressed sources, limits numerical libraries to one thread, writes the frozen protocol before fitting, and checkpoints predictions after each dataset. The verifier independently reads retained CSV files and recomputes every metric using Python's standard library.
