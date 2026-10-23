# Research consolidation and handoff-completion audit

Audit date: 2026-10-24. This document evaluates the requirements in
`HANDOFF_Dataset_Phase.md` against committed evidence. No workload was launched
for this audit.

## Completion rule and result

The four allowed dispositions are:

- **VERIFIED COMPLETE**: the stated bounded requirement is supported by
  repository evidence and its verification checks.
- **PARTIALLY COMPLETE**: useful verified evidence exists, but planned coverage,
  repetitions, representativeness, or protocol equivalence is incomplete.
- **NOT MEASURED**: no applicable measurement exists.
- **BLOCKED**: completion is unsafe or prevented by an identified external
  condition.

Approximate task-based completion is **58%**: VERIFIED COMPLETE = 1 point,
PARTIALLY COMPLETE = 0.5, and NOT MEASURED/BLOCKED = 0. The matrix below has
3 complete, 8 partial, and 1 blocked requirement: `(3 + 8×0.5) / 12 = 7/12`.
This is an audit heuristic, not a measured experimental percentage.

## Requirement matrix

| # | Requirement | Disposition | Evidence and boundary |
|---:|---|---|---|
| 1 | D1 Kaggle offline forecasting, six patterns | **VERIFIED COMPLETE** | All 600 scenarios, five models, and 1/4-step horizons: `results/dataset_phase/offline_results.md`, `offline_summary.csv`, `offline_per_scenario.csv`. Direct Kaggle identity: `kaggle_source_verification.json`. This is our rolling-origin protocol, not the paper's exact protocol. |
| 2 | D2 online-trace audit and early detection | **VERIFIED COMPLETE** | All 42 traces and 36 timing entries: `results/dataset_phase/online_results.md`, `online_trace_metrics.csv`, `online_early_detection_audit.csv`. These are authors' released runs, not new live repetitions. |
| 3 | Historical seasonal and burst experiments | **VERIFIED COMPLETE** | Three repeats × three controllers × two patterns: `results/results.md` and `results/runs/`. They measure capacity/CPU only; request QoS was not instrumented. |
| 4 | NASA live workload experiments | **PARTIALLY COMPLETE** | 3 accepted soft, 3 accepted Holt–Winters, 2 accepted tuned-HPA runs: `results/live_trace_phase/nasa_three_repeat/FINDINGS.md`, `mean_sd.csv`, `independent_verification.json`. Two repeat-3 tuned attempts were inconclusive under the unchanged 90% CPU-coverage rule, creating telemetry-based selection bias. This is an HTTP demand replay, not NASA forecast-MAPE reproduction. |
| 5 | Alibaba-derived workload experiments | **PARTIALLY COMPLETE** | One accepted run per controller: `results/live_trace_phase/alibaba_first_comparison/RESULTS.md`, `comparison.csv`, `evidence_manifest.json`. The first 42 observations of one container from a 16 MiB archive prefix are non-random and nonrepresentative; irregular source timing was replaced with equal replay bins. |
| 6 | On/off live experiments | **PARTIALLY COMPLETE** | One accepted run per controller: `results/live_trace_phase/onoff_first_comparison/RESULTS.md`, `comparison.csv`, `evidence_manifest.json`. No repeat variance; 90× compression and fixed order limit inference. |
| 7 | Growing live experiments | **PARTIALLY COMPLETE** | One accepted run per controller with independent verification: `results/live_trace_phase/growing_first_comparison/RESULTS.md`, `comparison.csv`, `independent_verification.json`. No repeat variance. |
| 8 | Stepped live experiments | **PARTIALLY COMPLETE** | Tuned HPA and Holt–Winters accepted; soft HPA retained as REJECT after dispatch p99 exceeded the frozen threshold: `results/live_trace_phase/stepped_first_comparison/RESULTS.md`, `comparison.csv`, `independent_verification.json`. This is not a complete three-controller matrix. |
| 9 | Chaotic live experiments | **BLOCKED** | One accepted soft-HPA run, two incomplete/excluded Holt–Winters attempts after host freezes, tuned HPA not run: `results/live_trace_phase/chaotic_first_comparison/SAFETY_STOP.md`, `safety_checkpoint.json`, `interrupted_runs/`. No chaotic cross-controller conclusion is valid. |
| 10 | Comparison with the original paper | **PARTIALLY COMPLETE** | Supported early-detection values are recomputed from released traces and the paper's headline claims are marked NOT MEASURED/NOT COMPARABLE in `docs/reproduction_report.md`. Exact +37.4%, Gemini 96.7%, and NASA/Alibaba sub-2% MAPE protocols were not recomputed. |
| 11 | Mean/SD and statistical comparisons | **PARTIALLY COMPLETE** | Sample SD and paired descriptive differences exist for historical seasonal/burst (`results/results.md`) and accepted NASA repetitions (`nasa_three_repeat/mean_sd.csv`, `paired_differences.csv`). Single-run live patterns have no SD or significance claims. |
| 12 | Reproducibility documentation and GitHub status | **PARTIALLY COMPLETE** | Plans, transformations, raw evidence, manifests, and reproduce files are indexed below. At audit start `main` was clean and two evidence commits (`0512669`, `b1fb564`) were local-only relative to `origin/main`; publication must be checked after the consolidation commit. |

## What is complete and what is not

Complete: exhaustive D1 evaluation, exhaustive audit of the supplied D2 release,
and the original repeated seasonal/burst capacity study. The bounded NASA,
Alibaba, on/off, growing, and stepped milestones produced valid evidence but do
not constitute a repeated six-pattern QoS matrix. Chaotic remains deliberately
incomplete for host safety. Paper forecasting MAPE and LLM classification were
not reproduced and must never be inferred from the live HTTP replays.

The documentation handoff can be finalized with these limitations. The wider
experimental programme cannot honestly be called complete.

## Strictly necessary remaining work

1. **Only recommended milestone — controlled repeated live-matrix completion on
   a resource-isolated host.** Preserve all current evidence as-is; add accepted
   repetitions for on/off, growing, and stepped, and only then retry the frozen
   chaotic three-controller protocol with hard host load, RAM, swap, disk-I/O,
   temperature, and client-concurrency abort guards. The target is at least
   three accepted runs per controller/pattern without changing acceptance rules.
   A different intensity must be labelled a new protocol, not a replacement.

Exact-paper offline/LLM reproduction would extend scope, but it is not required
to answer the calibrated-HPA research question because the unmatched headline
claims are already documented as NOT RECOMPUTED.

## Reproducibility and evidence-location index

| Evidence class | Primary locations |
|---|---|
| Authoritative handoff and methods | `HANDOFF_Dataset_Phase.md`; `docs/methodology.md`; `docs/reproduction_report.md`; `docs/LIVE_TRACE_PROTOCOL.md` |
| D1 offline forecast results | `results/dataset_phase/offline_results.md`; `offline_summary.csv`; `offline_per_scenario.csv`; `offline_paired_vs_persistence.csv`; `dataset_manifest.csv` |
| D2 released-trace audit | `results/dataset_phase/online_results.md`; `online_trace_metrics.csv`; `online_early_detection_audit.csv`; `online_manifest.csv` |
| Kaggle source identity | `results/dataset_phase/kaggle_source_verification.json`; `scripts/verify_kaggle_sources.py` |
| Historical seasonal/burst | `results/results.md`; `results/runs/repeat{1,2,3}/{seasonal,burst}/` |
| NASA replay | `results/live_trace_phase/nasa_three_repeat/FINDINGS.md`; `mean_sd.csv`; `paired_differences.csv`; `evidence_manifest.json`; `independent_verification.json` |
| Alibaba replay | `results/live_trace_phase/alibaba_first_comparison/RESULTS.md`; `DATASET_VALIDATION.md`; `WORKLOAD_TRANSFORMATION.md`; `comparison.csv`; `evidence_manifest.json` |
| On/off replay | `results/live_trace_phase/onoff_first_comparison/RESULTS.md`; `WORKLOAD_TRANSFORMATION.md`; `comparison.csv`; `evidence_manifest.json` |
| Growing replay | `results/live_trace_phase/growing_first_comparison/RESULTS.md`; `WORKLOAD_TRANSFORMATION.md`; `comparison.csv`; `independent_verification.json`; `evidence_manifest.json` |
| Stepped replay | `results/live_trace_phase/stepped_first_comparison/RESULTS.md`; `WORKLOAD_TRANSFORMATION.md`; `comparison.csv`; `independent_verification.json`; `evidence_manifest.json` |
| Chaotic safety checkpoint | `results/live_trace_phase/chaotic_first_comparison/SAFETY_STOP.md`; `safety_checkpoint.json`; `evidence_manifest.json`; `interrupted_runs/` |
| Integrated live interpretation | `results/live_trace_phase/results.md` |
| Local evidence policy | `docs/LOCAL_EVIDENCE_RETENTION.md` |

Raw data and failed/interrupted attempts are evidence and must not be cleaned,
rewritten, or silently promoted into accepted statistics.
