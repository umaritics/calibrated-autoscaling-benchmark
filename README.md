# Calibrated Autoscaling Benchmark

**When Does a Conservatively Tuned Reactive Baseline Beat a Predictive Autoscaler?**

Course research (FAST-NUCES Cloud Computing): reproduce the online core of
Duman & Eken (*J. Systems & Software*, 2026), then measure how a lightweight
Holt–Winters predictor compares to a soft 50% HPA and to a **conservatively tuned**
70% HPA on capacity (pod-seconds).

| | |
|---|---|
| Students | Muhammad Usman Al Haq (23i-0585), Muhammad Umar (23i-0782) |
| Paper | https://doi.org/10.1016/j.jss.2026.112861 |
| Upstream harness | https://github.com/syswe/workloads-predictional-scaling-operators |

## Submit these documents

- [`docs/reproduction_report.md`](docs/reproduction_report.md)
- [`docs/methodology.md`](docs/methodology.md)
- [`results/results.md`](results/results.md) — tables with mean ± SD, paired diffs, Cohen’s d

## Repository layout

```
policies/          Strawman HPA, tuned HPA (ours), Holt–Winters PHPA
manifests/         Sample app, load generator, metrics-server
scripts/           Experiment wrapper, analysis, upstream setup
results/           Measured CSVs (18 runs) + summary tables
docs/              Reproduction report + methodology
docs/course/       Proposal, development plan, literature matrix
upstream/          Instructions only (clone is gitignored)
```

## Main finding (3 repeats, cost/capacity only)

Holt–Winters uses **fewer pod-seconds** than the authors’ **50% HPA**.
A **70% conservatively tuned HPA** uses even fewer pod-seconds than Holt–Winters
on seasonal (all 3 repeats). Burst shows the same direction on average but high variance.
The tuned arm is also more **saturated** (higher hot fraction) — so this is **not**
an SLA / latency claim.

| Pattern | Strawman HPA | Holt–Winters | Tuned HPA 70% | HW adv. vs strawman | HW adv. vs tuned |
|---|---:|---:|---:|---:|---:|
| seasonal | 943 ± 94 | 767 ± 40 | 583 ± 80 | +176 ± 92 | −184 ± 42 |
| burst | 1088 ± 275 | 728 ± 46 | 653 ± 25 | +360 ± 265 | −75 ± 62 |

Units: pod-seconds (mean ± SD). Lower = less capacity held.

Paper / Kaggle online early-detection (HW vs HPA, not re-measured by us): seasonal 30.8 s, burst 20.5 s earlier.

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
./scripts/run_our_arm.sh 1 seasonal strawman_hpa
python scripts/analyze_our_results.py
```

## License

MIT. Upstream harness and operator retain their original licenses.

## Dataset extension

Both supplied Kaggle datasets are retained locally under `data/` (raw files and ZIP excluded from Git). The extension evaluates **all 600 synthetic scenarios across six patterns**, using five forecast variants at 15- and 60-minute horizons, and audits **all 42 authors’ online traces**. The original 18 live runs above remain separate evidence.

- [Offline metrics and paired comparisons](results/dataset_phase/offline_results.md)
- [Released online trace audit](results/dataset_phase/online_results.md)
- [Data layout and acquisition](data/README.md)
- [Status and remaining live/production-data work](docs/STATUS_DATASET_PHASE.md)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-datasets.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate_datasets.py
.venv/bin/python scripts/verify_dataset_results.py
```

The authors’ released early-detection arithmetic is reproducible, but earlier scaling does not imply lower capacity: their HW trace holds more time-averaged ready replicas than their HPA trace on every pattern. The release contains inconsistent ready/current counts and only one run per condition, so this is descriptive evidence. No new live trials, NASA/Alibaba evaluation, or latency measurements are claimed.

Offline result: at 15 minutes, persistence has the lowest mean MAE on burst, chaotic, growing and stepped; gradient boosting leads seasonal and onoff. See the [computed pattern/horizon rankings](results/results.md#lowest-mean-mae-among-the-five-evaluated-variants). Forecast rankings alone do not establish autoscaling cost or QoS.
