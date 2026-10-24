# Submission checklist

Repository: <https://github.com/umaritics/calibrated-autoscaling-benchmark>

Submit or review these entry points:

1. `README.md` — executive summary, findings, coverage, and verification.
2. `docs/STATUS_DATASET_PHASE.md` — final handoff decision and authoritative
   experiment inventory.
3. `docs/reproduction_report.md` — sources, environment, deviations, paper
   comparison, and reproduction commands.
4. `docs/methodology.md` — controllers, design, metrics, acceptance, statistics,
   and validity threats.
5. `results/live_trace_phase/results.md` — integrated live QoS/capacity results.
6. `results/dataset_phase/offline_results.md` and
   `results/real_world_forecasting/RESULTS.md` — forecasting results.

One-sentence conclusion:

> Lightweight prediction improved measured QoS under several overload replays,
> but at a large capacity penalty; once the reactive baseline was conservatively
> tuned, it was more capacity-efficient whenever all controllers already served
> the tested workload successfully, so the advantage is workload- and
> calibration-dependent rather than universal.

Status: **COMPLETE WITH DOCUMENTED LIMITATIONS**. This is not an exhaustive
repeated six-pattern production study. No mandatory handoff item remains; more
isolated live repetitions are optional future work.
