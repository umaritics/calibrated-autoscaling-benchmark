# Calibrated Autoscaling Benchmark

**Final handoff status: COMPLETE WITH DOCUMENTED LIMITATIONS.**

This repository asks: **under which workload patterns does lightweight
predictive autoscaling outperform a soft reactive HPA, and how much does that
advantage change when the reactive baseline is conservatively tuned?** It
compares the paper-aligned 50% CPU HPA, a 70% CPU / slow-scale-down HPA, and a
Holt–Winters predictive HPA using offline forecasts, released traces, and live
Kubernetes replays.

The bounded handoff is complete: saved evidence, source hashes, acceptance
decisions, forecasting outputs, reproduction instructions, and limitations are
published. It is **not** an exhaustive repeated six-pattern production study.
Most newer live patterns have one accepted run per controller; rejected,
inconclusive, and interrupted attempts remain visible.

| | |
|---|---|
| Students | Muhammad Usman Al Haq (23i-0585), Muhammad Umar (23i-0782) |
| Course | FAST-NUCES Cloud Computing research |
| Base paper | Duman & Eken, *From Reactive to Predictive…*, JSS (2026), <https://doi.org/10.1016/j.jss.2026.112861> |
| Upstream online harness | <https://github.com/syswe/workloads-predictional-scaling-operators> |

## Executive research summary

The predictor's advantage depends on whether extra capacity prevents overload.
In the NASA-derived and on/off overload replays, Holt–Winters materially reduced
request errors and successful-request latency, but consumed much more capacity.
In the accepted tuned-versus-predictive stepped comparison, it reduced errors
from 17.58% to 1.01% at a 121.80% pod-second penalty. These are descriptive
results, not significance claims.

When all controllers already served the workload without errors, predictive
overprovisioning did not help observed QoS. Tuned HPA used the least capacity in
the growing replay (1,572.50 pod-s) and guarded chaotic replay (990.00 pod-s).
In the Alibaba-derived replay, soft HPA used slightly less than tuned HPA
(1,277.50 versus 1,317.50 pod-s); both beat Holt–Winters (1,422.50 pod-s). The
older seasonal/burst study also found that tuning reversed Holt–Winters' capacity
advantage over the soft HPA, but those runs did not record request QoS.

No local transition measurement proves genuine anticipation. Earlier response
can also result from higher starting replicas, controller cadence, or aggressive
scaling. The evidence supports a **capacity–QoS tradeoff conditioned on workload
stress and baseline calibration**, not “predictive always wins” or “reactive
always wins.”

## Verified live coverage

`n` counts accepted repetitions. Error and latency were not collected in the
historical seasonal/burst study. The original and guarded chaotic protocols are
scientifically separate and are never pooled.

| Workload | Soft HPA | Tuned HPA | Holt–Winters | Main disposition |
|---|---:|---:|---:|---|
| Seasonal, historical | n=3 | n=3 | n=3 | Capacity/CPU only |
| Burst, historical | n=3 | n=3 | n=3 | Capacity/CPU only |
| NASA-derived | n=3 | n=2 | n=3 | Two tuned repeat-3 attempts inconclusive |
| Alibaba-derived | n=1 | n=1 | n=1 | All accepted, zero request errors |
| On/off | n=1 | n=1 | n=1 | All accepted; overload observed |
| Growing | n=1 | n=1 | n=1 | All accepted, zero request errors |
| Stepped | rejected | n=1 | n=1 | Soft arm failed frozen dispatch-integrity threshold |
| Chaotic, original 20–120 RPS | n=1 | not run | 0 | Two predictive attempts interrupted by host freezes |
| Guarded chaotic, 10–45 RPS | n=1 | n=1 | n=1 | All accepted, zero request errors |

The authoritative measurements and limitations are in
[`results/live_trace_phase/results.md`](results/live_trace_phase/results.md).
The definitive experiment inventory is in
[`docs/STATUS_DATASET_PHASE.md`](docs/STATUS_DATASET_PHASE.md).

## Forecasting evidence

- **D1 synthetic:** all 600 scenarios across burst, chaotic, growing, on/off,
  seasonal, and stepped; five model variants; rolling 15- and 60-minute
  horizons. Persistence had the lowest 15-minute mean MAE on four patterns;
  GBDT led seasonal and on/off. See
  [`results/dataset_phase/offline_results.md`](results/dataset_phase/offline_results.md).
- **D2 released online traces:** all 42 traces and 36 early-detection records
  audited. Released Holt–Winters first-desired-increase advantages range from
  20.48 to 40.93 seconds. This reproduces arithmetic on authors' data, not new
  live evidence. See
  [`results/dataset_phase/online_results.md`](results/dataset_phase/online_results.md).
- **NASA raw log:** 7,938 complete five-minute request-count bins, chronological
  60/20/20 split. Best GBDT MAE/RMSE/WAPE: 36.3206/47.8176/18.5139% at five
  minutes and 50.8335/66.6083/25.8498% at 60 minutes.
- **Alibaba raw prefix:** 3,489 native ten-second mean CPU-utilization points,
  chronological 60/20/20 split. Best GBDT MAE/RMSE/WAPE:
  1.7249/2.1295/14.4921% at ten seconds and 1.7271/2.1328/14.5218% at 60
  seconds. NASA request counts and Alibaba CPU percentages are different targets
  and are not compared numerically.

The paper's NASA/Alibaba sub-2% MAPE values were **not reproduced**: exact
machines, split, horizon, features, and zero-target rule are unavailable, and
our targets/protocol differ. Full results are in
[`results/real_world_forecasting/RESULTS.md`](results/real_world_forecasting/RESULTS.md).

## Controllers

- Soft HPA: 50% target CPU, 60-second scale-down stabilization, 1–20 replicas.
- Tuned HPA: 70% target CPU, 300-second scale-down stabilization, scale-up capped
  at four pods per 60 seconds, 1–20 replicas.
- Holt–Winters PHPA: 50% target CPU; alpha 0.9, beta 0.2, gamma 0.3;
  `seasonalPeriods=6`, `storedSeasons=4`, ten-second sync, 1–20 replicas.

Exact manifests are under [`policies/`](policies/).

## Reproduce and verify

Create the research environment and run the lightweight checks:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-datasets.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_dataset_results.py
.venv/bin/python scripts/verify_real_world_forecasting.py
```

The last verifier refreshes its verification JSON/manifest. Dataset acquisition,
local-only files, exact forecast commands, and live prerequisites are documented
in [`data/README.md`](data/README.md),
[`docs/reproduction_report.md`](docs/reproduction_report.md), and each live
experiment's `REPRODUCE.md`. Accepted live runs are intentionally not overwritten;
do not launch them merely to verify the committed evidence.

## Submission map

- [Final handoff and experiment inventory](docs/STATUS_DATASET_PHASE.md)
- [Reproduction report and paper comparison](docs/reproduction_report.md)
- [Methodology and validity threats](docs/methodology.md)
- [Integrated live results](results/live_trace_phase/results.md)
- [Historical seasonal/burst results](results/results.md)
- [Offline D1 and released D2 results](results/dataset_phase/offline_results.md)
- [NASA/Alibaba forecast results](results/real_world_forecasting/RESULTS.md)
- [Local evidence-retention policy](docs/LOCAL_EVIDENCE_RETENTION.md)

## Repository layout

```text
policies/       Controller definitions
manifests/      Kubernetes application and infrastructure manifests
scripts/        Evaluation, live-run, safety, and verification code
results/        Raw retained measurements, summaries, hashes, and manifests
docs/           Methodology, reproduction, status, and course documents
data/           Acquisition instructions; large/raw sources are gitignored
```

## License

MIT. Upstream datasets, harnesses, and operators retain their own licenses.
