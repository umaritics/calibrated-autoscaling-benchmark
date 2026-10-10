# Calibrated Autoscaling Benchmark

**When Does a Calibrated Reactive Baseline Beat a Predictive Autoscaler?**

Course research (FAST-NUCES Cloud Computing): reproduce the online core of
Duman & Eken (*J. Systems & Software*, 2026), then measure how much of a
Holt–Winters predictive advantage disappears once Kubernetes HPA is fairly tuned.

| | |
|---|---|
| Students | Muhammad Usman Al Haq (23i-0585), Muhammad Umar (23i-0782) |
| Paper | https://doi.org/10.1016/j.jss.2026.112861 |
| Upstream harness | https://github.com/syswe/workloads-predictional-scaling-operators |

## Repository layout

```
policies/          Strawman HPA, calibrated HPA (ours), Holt–Winters PHPA
manifests/         Sample app, load generator, metrics-server
scripts/           Experiment wrapper, analysis, upstream setup
results/           Measured CSVs (18 runs) + summary tables
docs/              Reproduction report + methodology
docs/course/       Proposal, development plan, literature matrix
upstream/          Instructions only (clone is gitignored)
```

## Main finding (3 repeats, Docker Desktop Kubernetes)

Holt–Winters beats the authors' **50% HPA** on pod-seconds, but a **70% calibrated HPA**
uses even fewer pod-seconds than Holt–Winters on both seasonal and burst patterns.
The predictive advantage was largely a weak-baseline artifact.

| Pattern | Strawman HPA | Holt–Winters | Calibrated HPA | Calibration gap |
|---|---:|---:|---:|---:|
| seasonal | 978.92 | 800.11 | 608.54 | 370.38 |
| burst | 1122.98 | 735.51 | 668.09 | 454.89 |

Units: mean pod-seconds (lower = less capacity used). Full tables: [`results/results.md`](results/results.md).

## Quick start (reproduce)

1. Enable Kubernetes in Docker Desktop (≥4 CPU, ≥8 GB RAM).
2. Install `kubectl`, `helm`, Python 3.10+.
3. Install the PHPA operator (see `upstream/README.md`).
4. From this repo:

```bash
./scripts/setup_from_upstream.sh
cd upstream/workloads-predictional-scaling-operators
python3 -m venv .venv && source .venv/bin/activate
pip install numpy pandas matplotlib
# ensure metrics-server + sample app (make bootstrap, or apply manifests/)
./scripts/run_our_arm.sh 1 seasonal strawman_hpa
./scripts/run_our_arm.sh 1 seasonal holtwinters
./scripts/run_our_arm.sh 1 seasonal calibrated_hpa
python scripts/analyze_our_results.py
```

## Deliverable documents

- [`docs/reproduction_report.md`](docs/reproduction_report.md)
- [`docs/methodology.md`](docs/methodology.md)

## License

MIT. Upstream harness and operator retain their original licenses.
