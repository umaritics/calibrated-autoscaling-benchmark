# Research consolidation and handoff-completion audit

Audit date: 2026-10-24. This document evaluates the requirements in
`HANDOFF_Dataset_Phase.md` against committed evidence. No workload was launched
for this audit.

## Task 11 update — real-world forecasting complete

The later Task 11 forecast-accuracy milestone is **VERIFIED COMPLETE under its
independent protocol**. It adds real held-out NASA and Alibaba predictions for
four models and two horizons per dataset, 7 focused tests, and an independent
51-check verifier. The result is not an exact paper reproduction: the accessible
sources do not disclose the real-world split, horizon, feature construction,
zero-target rule, or Alibaba machine identifiers. Evidence is under
`results/real_world_forecasting/`; source data remain local and ignored.

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
| 9 | Chaotic live experiments | **PARTIALLY COMPLETE** | The original hazardous 20–120 RPS variant remains safety-stopped. A separate prospectively corrected 10–45 RPS guarded variant has one independently accepted run per controller: all arms served 12,532/12,532 requests; tuned/PHPA/soft used 990.000/1342.499/1185.000 pod-seconds. Task 12's failed smoke remains failed; protocol v2 documents scheduler-affinity enforcement after diagnosing absent cpuset delegation: `results/live_trace_phase/chaotic_first_comparison/SAFETY_STOP.md`; `results/live_trace_phase/guarded_chaotic_comparison/FINDINGS.md`; `affinity_revision_v2/SAFETY_PROTOCOL_V2.md`. No repeat variance and no pooling across intensities. |
| 10 | Comparison with the original paper | **PARTIALLY COMPLETE** | Supported early-detection values are recomputed from released traces and the paper's headline claims are marked NOT MEASURED/NOT COMPARABLE in `docs/reproduction_report.md`. Exact +37.4%, Gemini 96.7%, and NASA/Alibaba sub-2% MAPE protocols were not recomputed. |
| 11 | Mean/SD and statistical comparisons | **PARTIALLY COMPLETE** | Sample SD and paired descriptive differences exist for historical seasonal/burst (`results/results.md`) and accepted NASA repetitions (`nasa_three_repeat/mean_sd.csv`, `paired_differences.csv`). Single-run live patterns have no SD or significance claims. |
| 12 | Reproducibility documentation and GitHub status | **PARTIALLY COMPLETE** | Plans, transformations, raw evidence, manifests, and reproduce files are indexed below. Task 12 was published at `73c59b9`; Task 13's publication status is reported in its final handoff. |

## What is complete and what is not

Complete: exhaustive D1 evaluation, exhaustive audit of the supplied D2 release,
and the original repeated seasonal/burst capacity study. The bounded NASA,
Alibaba, on/off, growing, stepped, and guarded chaotic milestones produced valid evidence but do
not constitute a repeated six-pattern QoS matrix. The hazardous chaotic variant
remains stopped; the lower-intensity guarded matrix is complete at n=1. Paper forecasting MAPE and LLM classification were
not reproduced and must never be inferred from the live HTTP replays.

The documentation handoff can be finalized with these limitations. The wider
experimental programme cannot honestly be called complete.

## Strictly necessary remaining work

1. **Only recommended milestone — controlled repeated live-matrix completion on
   a resource-isolated host.** Preserve all current evidence as-is; add accepted
   repetitions for on/off, growing, stepped, and the guarded chaotic variant
   with the existing hard host load, RAM, swap, disk-I/O, and client-concurrency
   abort guards. The target is at least
   three accepted runs per controller/pattern without changing acceptance rules.
   The guarded chaotic n=1 result may be extended prospectively but must remain
   separate from the hazardous intensity.

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
| Guarded chaotic variant | `results/live_trace_phase/guarded_chaotic_comparison/FINDINGS.md`; `affinity_revision_v2/SAFETY_PROTOCOL_V2.md`; `affinity_revision_v2/smoke_gate.json`; `comparison.csv`; `independent_verification.json`; `evidence_manifest.json` |
| Integrated live interpretation | `results/live_trace_phase/results.md` |
| Real-world forecasting | `results/real_world_forecasting/RESULTS.md`; `metrics.csv`; `predictions.csv`; `evaluation_protocol.json`; `independent_verification.json`; `PAPER_COMPARISON.md`; `evidence_manifest.json` |
| Local evidence policy | `docs/LOCAL_EVIDENCE_RETENTION.md` |

Raw data and failed/interrupted attempts are evidence and must not be cleaned,
rewritten, or silently promoted into accepted statistics.
