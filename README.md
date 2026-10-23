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

The authors’ released early-detection arithmetic is reproducible, but earlier scaling does not imply lower capacity: their HW trace holds more time-averaged ready replicas than their HPA trace on every pattern. The release contains inconsistent ready/current counts and only one run per condition, so this is descriptive evidence.

## NASA-derived live checkpoint

A later live phase replayed one fixed NASA-HTTP-derived demand shape against the
benchmark Kubernetes service with request-level latency/error collection. It is
an eight-of-nine accepted matrix: soft HPA 3/3, tuned HPA 2/3, and Holt–Winters
3/3. Two retained attempts for tuned-HPA repeat 3 are `INCONCLUSIVE` because
CPU telemetry covered 75/84 samples, below the frozen 90% rule. They are not
promoted into the aggregates. Because missing metrics overlap service
instability, the incomplete matrix may favor healthier periods.

See [NASA findings](results/live_trace_phase/nasa_three_repeat/FINDINGS.md),
[independent verification](results/live_trace_phase/nasa_three_repeat/independent_verification.json),
and the [evidence manifest](results/live_trace_phase/nasa_three_repeat/evidence_manifest.json).

## Alibaba-derived live checkpoint

One frozen, three-controller comparison is complete and all arms passed the
acceptance framework. The input is the first 42 observations of `c_1` found in
a 16 MiB byte-range prefix of Alibaba Cluster Trace v2018. It is neither random
nor representative. The transformation maps irregular CPU-utilization samples
to equal ten-second HTTP-demand bins, so this is an explicitly time-warped
benchmark replay, not Alibaba workload reproduction.

All arms recorded 14,420/14,420 successful measurement requests. Pod-seconds
were 1277.50 (soft HPA), 1317.50 (tuned HPA), and 1422.50 (Holt–Winters).
With one repetition, these values are descriptive only. See the
[comparison report](results/live_trace_phase/alibaba_first_comparison/RESULTS.md)
and [dataset audit](results/live_trace_phase/alibaba_first_comparison/DATASET_VALIDATION.md).

Offline result: at 15 minutes, persistence has the lowest mean MAE on burst, chaotic, growing and stepped; gradient boosting leads seasonal and onoff. See the [computed pattern/horizon rankings](results/results.md#lowest-mean-mae-among-the-five-evaluated-variants). Forecast rankings alone do not establish autoscaling cost or QoS.

## Genuine NASA/Alibaba forecasting evaluation

The raw July NASA log and the bounded Alibaba container-usage prefix now have a
separate leakage-safe forecasting evaluation. NASA contributes 7,938 complete
5-minute request-count bins; Alibaba contributes a deterministic 3,489-point
native 10-second CPU series formed only where at least 20 complete-prefix
containers have real observations. No Alibaba gap is filled or mapped to an
artificial interval.

Across persistence, moving average, exponential smoothing, and histogram GBDT,
GBDT has the lowest held-out MAE at both horizons. NASA GBDT MAE is 36.3206 at
5 minutes and 50.8335 at 60 minutes (requests/5 minutes). Alibaba GBDT MAE is
1.7249 at 10 seconds and 1.7271 at 60 seconds (CPU percentage points). These
targets are not comparable to each other. The authors' real-world MAPE values
are also not directly comparable because their exact split, horizon, features,
zero rule, and Alibaba machine selection are unavailable.

See the [full forecast results](results/real_world_forecasting/RESULTS.md),
[paper comparison](results/real_world_forecasting/PAPER_COMPARISON.md), and
[independent verification](results/real_world_forecasting/independent_verification.json).

## Growing-pattern live checkpoint

One frozen D1-derived growing replay was executed once per controller, with all
three arms accepted by the established analyzer and independent verifier. All
92,199 measurement requests succeeded. Pod-seconds were 1,927.50 (soft HPA),
1,572.50 (tuned HPA), and 2,897.50 (Holt–Winters). Holt–Winters responded
earliest at the predeclared sustained-growth threshold, but held substantially
more capacity; this is descriptive evidence from one 90×-accelerated synthetic
pod-demand-proxy replay, not native-timing traffic or a significance result.

See the [growing comparison report](results/live_trace_phase/growing_first_comparison/RESULTS.md),
[frozen plan](results/live_trace_phase/growing_first_comparison/frozen_plan.json),
and [independent verification](results/live_trace_phase/growing_first_comparison/independent_verification.json).

## Stepped-pattern live checkpoint

A deterministic D1 scenario-62 window was replayed for 1,200 seconds so each
400-second plateau outlasted the tuned HPA's unchanged 300-second scale-down
stabilization. Tuned HPA and Holt–Winters were accepted; the soft-HPA arm was
retained but rejected because generator dispatch p99 (0.315 s) exceeded the
frozen 0.100-second threshold. Among accepted arms, Holt–Winters reduced errors
from 17.58% to 1.01% but used 121.80% more ready-pod-seconds than tuned HPA.
Neither controller pre-scaled before the observed upward step, both had zero
post-step failures, and tuned HPA was competitive at that transition.

See the [stepped comparison report](results/live_trace_phase/stepped_first_comparison/RESULTS.md),
[frozen plan](results/live_trace_phase/stepped_first_comparison/frozen_plan.json),
and [independent verification](results/live_trace_phase/stepped_first_comparison/independent_verification.json).

## Chaotic-pattern safety checkpoint

A deterministic D1 scenario-1 window (indices 284–325) was frozen before
execution and mapped to the established 20–120 RPS, 420-second protocol. The
soft-HPA arm completed and passed the evidence-integrity analyzer, but 85.47%
of scheduled requests failed and host one-minute load reached 106.35. The host
then became unresponsive during two separate Holt–Winters attempts. Both
partial attempts are retained and excluded; tuned HPA was not started. No
three-controller chaotic comparison or scaling conclusion is claimed.

See the [safety-stop report](results/live_trace_phase/chaotic_first_comparison/SAFETY_STOP.md),
[frozen plan](results/live_trace_phase/chaotic_first_comparison/frozen_plan.json),
and [checkpoint](results/live_trace_phase/chaotic_first_comparison/safety_checkpoint.json).
