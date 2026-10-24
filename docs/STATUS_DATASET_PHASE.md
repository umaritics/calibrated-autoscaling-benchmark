# Final research handoff

Audit date: 2026-10-24
Status: **COMPLETE WITH DOCUMENTED LIMITATIONS**

The flexible success criteria in `HANDOFF_Dataset_Phase.md` are satisfied. The
repository contains computed multi-pattern forecasting results, additional live
pattern evidence, an explicit comparison with the paper, reproducible source and
artifact provenance, and a synchronized publication workflow. This closes the
bounded handoff; it does **not** declare the broader research programme to be an
exhaustive repeated six-pattern statistical study.

No mandatory handoff requirement remains outstanding. Repeating the single-run
live matrices on isolated hardware would strengthen external validity, but is
optional future research rather than a condition for honest handoff closure.

## Controller definitions used in live comparisons

| Controller | Exact configuration | Source |
|---|---|---|
| Soft reactive HPA (`strawman_hpa`) | CPU target 50%; scale-up stabilization 0 s; scale-down stabilization 60 s; min/max 1/20 | `policies/hpa-baseline.yaml` |
| Conservatively tuned HPA (`calibrated_hpa`) | CPU target 70%; scale-up stabilization 0 s; at most +4 pods/60 s; scale-down stabilization 300 s and at most 50%/60 s; min/max 1/20 | `policies/hpa-calibrated.yaml` |
| Holt–Winters PHPA (`holtwinters`) | CPU target 50%; alpha .9, beta .2, gamma .3; additive trend/season; `seasonalPeriods=6`; `storedSeasons=4`; sync 10 s; min/max 1/20 | `policies/phpa-holtwinters.yaml` |

The predictor was not retuned per workload. That preserves comparability of the
controller configuration but can create workload-specific season mismatch.

## Authoritative live experiment inventory

Metrics are request error rate / successful-request p95 / ready-pod-seconds.
Historical seasonal/burst rows did not collect request outcomes. `n` counts only
accepted repetitions; rejected, inconclusive, and interrupted attempts are kept
separate. Every controller used the configuration above.

| Workload and source | Replay protocol | Accepted evidence by controller | Excluded attempts | Principal measured result | Evidence and comparability boundary |
|---|---|---|---|---|---|
| Seasonal, historical synthetic harness | 120 s collection, 30 s warmup, nominal 5 s sampling | Soft n=3; tuned n=3; HW n=3 | None | Pod-s: soft 943.01 ± 94.07; tuned 583.25 ± 79.59; HW 766.80 ± 39.61 | `results/results.md`, `results/runs/`; capacity/CPU only, no latency/errors; HW 60 s season mismatched roughly 80 s load period |
| Burst, historical synthetic harness | Same 120/30 s protocol; shortened window covers only part of the original burst sequence | Soft n=3; tuned n=3; HW n=3 | None | Pod-s: soft 1088.25 ± 274.75; tuned 653.40 ± 24.74; HW 728.38 ± 46.49 | `results/results.md`, `results/runs/`; capacity/CPU only and high soft-HPA variance |
| NASA-derived HTTP request series | One fixed normalized schedule; 120 s warmup + 420 s measurement on single-node kind | Soft n=3; tuned n=2; HW n=3 | Two tuned repeat-3 attempts `INCONCLUSIVE` at 75/84 CPU samples, below frozen 90% threshold | Soft 44.76% ± 9.37% / 2.508 ± .918 s / 1192.50 ± 156.12; tuned 37.75% ± 2.34% / 2.241 ± .306 s / 915.00 ± 17.68; HW 18.04% ± 2.05% / .868 ± .653 s / 3479.17 ± 20.21 | `results/live_trace_phase/nasa_three_repeat/FINDINGS.md`, `mean_sd.csv`; replay of demand against benchmark service, not NASA infrastructure or forecast-MAPE reproduction; telemetry exclusions may bias tuned aggregate |
| Alibaba-derived live | First 42 observations of `c_1` from bounded v2018 prefix; irregular source time warped to 42 × 10 s bins; 6.21–120 RPS; 120 s warmup + 420 s measurement | Soft n=1; tuned n=1; HW n=1 | None | All 14,420 requests succeeded. Pod-s: soft 1277.50; tuned 1317.50; HW 1422.50 | `results/live_trace_phase/alibaba_first_comparison/`; non-random container/prefix, CPU-to-RPS mapping, nonlinear time warp; descriptive only |
| On/off D1 scenario 81 | First 42 15-minute observations; 90× compression to 10 s bins; 120 s warmup + 420 s measurement; up to 120 RPS | Soft n=1; tuned n=1; HW n=1 | None | Soft 50.05% / 1.456 s / 1612.50; tuned 48.55% / 1.069 s / 1332.50; HW 13.29% / .050 s / 3542.50 | `results/live_trace_phase/onoff_first_comparison/`; synthetic pod proxy mapped to HTTP RPS, one transition each direction, fixed order |
| Growing D1 scenario 1 | Deterministically selected 42-point rising window; 90× compression; 20–120 RPS; 120 s warmup + 420 s measurement | Soft n=1; tuned n=1; HW n=1 | None | All 30,733 requests succeeded. Pod-s: soft 1927.50; tuned 1572.50; HW 2897.50 | `results/live_trace_phase/growing_first_comparison/`; HW reacted earlier but began/held more capacity, so anticipation is not established |
| Stepped D1 scenario 62 | 120 selected observations; 90× compression; three 400 s plateaus; 20–120 RPS; 120 s warmup + 1,200 s measurement | Tuned n=1; HW n=1 | Soft n=0: `REJECT`, dispatch p99 .3148 s > frozen .100 s threshold | Tuned 17.58% / .011 s / 5872.50; HW 1.01% / .016 s / 13025.00 | `results/live_trace_phase/stepped_first_comparison/`; neither accepted arm pre-scaled before analyzed upward step; rejected soft result not promoted |
| Chaotic original D1 scenario 1 | 42 × 10 s bins; 90× compression; 20–120 RPS; max in-flight 2,048; 120 s warmup + 420 s measurement | Soft n=1 | HW n=0: two host-freeze interruptions; tuned not run after safety stop | Soft 85.47% / 4.482 s / 685.00; host load reached 106.35 | `results/live_trace_phase/chaotic_first_comparison/`; no cross-controller conclusion; hazardous protocol remains stopped |
| Guarded chaotic D1 scenario 1 | Same 42-bin source window but a separate 10–45 RPS transform; max 256 in flight; 120 s warmup + 420 s measurement; watchdog/resource/affinity gates | Soft n=1; tuned n=1; HW n=1 | Task 12 smoke attempt remains failed; accepted matrix used prospectively revised affinity validation | All 12,532 requests succeeded. Pod-s: soft 1185.00; tuned 990.00; HW 1342.50 | `results/live_trace_phase/guarded_chaotic_comparison/`; not a repetition/repair of 20–120 RPS run; fixed order and n=1 |

Raw capacity is compared only within an identical workload, transform, duration,
and acceptance protocol. Results from different source-to-RPS mappings are not
averaged. Error rates include all scheduled measurement requests; latency
percentiles include successful requests only.

## Forecasting inventory

### D1 synthetic six-pattern evaluation

- Coverage: all 600 scenarios (100 per pattern), 2,688 train and 672 test samples
  per scenario at 15-minute cadence; no sampling/exclusions.
- Method: rolling origin at 1 and 4 steps (15 and 60 minutes); models are
  persistence, six-sample moving average, fixed-period Holt–Winters,
  train-validation-selected Holt–Winters, and histogram GBDT.
- Counts: 672 predictions/scenario/model at horizon 1 and 669 at horizon 4;
  6,000 scenario/model/horizon metric rows.
- Metrics: MAE, RMSE, nonzero-only MAPE, and WAPE; units are synthetic pods.
- Lowest mean MAE at 15 minutes: burst persistence 1.0375; chaotic persistence
  2.6700; growing persistence .3659; on/off GBDT 5.5859; seasonal GBDT .5326;
  stepped persistence .6099. Full 60-minute rankings and every metric are in
  `results/dataset_phase/offline_results.md` and `offline_summary.csv`.
- Boundary: this is our leakage-safe protocol, not the paper's exact +37.4%
  comparison protocol, and forecasting rank does not establish live QoS/cost.

### D2 released online audit

All 42 authors' released traces and all 36 timing summaries were audited.
Recomputed first-desired-increase advantages match within 1e-9 seconds: burst
20.48, chaotic 30.85, growing 30.72, on/off 40.93, seasonal 30.77, and stepped
30.71 seconds. This is reproduced arithmetic on released values, not an
independent live repetition or proof of peak anticipation. Evidence:
`results/dataset_phase/online_results.md`, `online_trace_metrics.csv`, and
`online_early_detection_audit.csv`.

### Genuine NASA and Alibaba forecasting

| Dataset / target | Coverage and split | Horizons | Models | Best held-out result | Counts and source evidence |
|---|---|---|---|---|---|
| NASA HTTP request count per complete 5-minute bin | 7,938 bins; chronological 4,762/1,588/1,588 train/validation/test | 5 min and 60 min | Persistence, moving average, exponential smoothing, GBDT | GBDT 5 min: MAE 36.3206, RMSE 47.8176, MAPE 41.6072%, WAPE 18.5139%, n=1,588. GBDT 60 min: 50.8335, 66.6083, 65.2408%, 25.8498%, n=1,577 | `results/real_world_forecasting/nasa_series.csv`, `metrics.csv`, `preprocessing_metadata.json`, `evidence_manifest.json` |
| Alibaba mean `cpu_util_percent` at native 10-second timestamps | 3,489 points; chronological 2,093/698/698 train/validation/test; at least 20 genuine completed-prefix containers per timestamp | 10 s and 60 s | Same four model classes | GBDT 10 s: MAE 1.7249 percentage points, RMSE 2.1295, MAPE 15.2773%, WAPE 14.4921%, n=698. GBDT 60 s: 1.7271, 2.1328, 15.2691%, 14.5218%, n=693 | `results/real_world_forecasting/alibaba_series.csv`, `metrics.csv`, `preprocessing_metadata.json`, `evidence_manifest.json` |

MAPE excludes zero actuals and reports the excluded count; MAE/RMSE/WAPE/sMAPE
include every aligned pair. NASA request counts and Alibaba CPU percentages have
different meanings and scales and are never pooled.

## Original paper comparison

| Claim/result | Original | Ours | Difference / comparability |
|---|---|---|---|
| Seasonal early detection | 30.8 s earlier (released summary) | 30.77 s recomputed | Released-value arithmetic reproduced; not a new live replication |
| Burst early detection | 20.5 s earlier | 20.48 s recomputed | Same boundary |
| NASA/Alibaba GBDT MAPE | 1.36% / .75% in authors' public repository; abstract says sub-2% | 41.6072%/65.2408% NASA and 15.2773%/15.2691% Alibaba at our two horizons | **Not directly comparable:** target construction, machine selection, split, horizons, features, and zero rule differ; no valid “difference” is computed |
| Pattern-specific forecast improvement | +37.4% | NOT RECOMPUTED | Paper denominator/exact comparison unavailable; D1 results use our documented rolling protocol |
| Gemini classification | 96.7% | NOT MEASURED | Optional LLM component outside the calibrated-baseline research contribution |
| Local live request QoS/pod-seconds | No directly matching published table | Measured as inventoried above | Independently measured under different replay protocols; not forecast MAPE |

See `docs/reproduction_report.md` and
`results/real_world_forecasting/PAPER_COMPARISON.md` for provenance.

## Statistical and validity audit

- Mean ± sample SD is legitimate for the historical seasonal/burst groups
  (n=3/controller/pattern) and for accepted NASA groups (soft/HW n=3; tuned n=2).
- NASA paired summaries use only matching accepted repeats; tuned comparisons
  therefore have n=2 and are explicitly limited.
- D1 SD is variability across 100 different scenarios, not repeated execution
  variance.
- Every other accepted live controller-pattern group has n=1 and is descriptive
  only. No SD, significance, or production generalization is claimed.
- Rejected stepped soft HPA, inconclusive NASA tuned attempts, interrupted
  original-chaotic HW attempts, and the failed guarded smoke remain separate.
- Fixed run order, host contention, single-node kind, startup state, controller
  cadence, application restarts, temporal compression, differing intensity,
  transformation choice, and absent backend identity constrain causal inference.
- Pod-seconds quantify ready capacity, not price or service quality. Successful-
  request latency must be read beside the scheduled-request error rate.

## Research answer

Lightweight prediction helped measured QoS when the reactive systems were
overloaded: NASA-derived, on/off, and the accepted tuned-versus-HW stepped
comparison. The gain was purchased with substantial overprovisioning. Tuned HPA
was competitive when the load was serviceable without that extra capacity:
growing and guarded chaotic had zero errors for all arms and tuned used least
capacity; Alibaba-derived also had zero errors and soft HPA was marginally leaner
than tuned. Historical seasonal/burst capacity results show how a soft 50%
baseline can exaggerate the predictor's capacity advantage, but cannot establish
QoS equivalence.

No local result demonstrates genuine proactive anticipation. Baseline calibration
shrinks or reverses the apparent predictive advantage, but the amount is
workload- and protocol-dependent; it is not a universal scalar correction.

## Verification completed for this handoff

- 37/37 automated unit/evidence tests passed.
- Dataset verifier passed: manifests, 6,000 model results, all aggregates, 1,200
  independently recalculated persistence errors, 42 trace integrals, and 36
  timing matches.
- Real-world forecast verifier passed 55 checks over 18,224 prediction rows and
  16 metric groups.
- 263 unique saved-artifact path/hash entries across nine evidence manifests
  matched current files.
- Historical manifests contain time-scoped hashes of the runner version used
  when each experiment was generated. Later safety revisions changed the current
  `scripts/live/run_trace.py`; those old code hashes are provenance, not an
  assertion that today's path has the old digest. Git history retains each
  referenced code state. Raw/run artifact hashes remain valid.

No live workload, Docker cluster, or full forecasting recomputation was launched
for this final audit.

## Reproduction and evidence index

| Evidence | Primary entry point |
|---|---|
| Executive overview | `README.md` |
| Methods and validity | `docs/methodology.md` |
| Environment, sources, paper comparison | `docs/reproduction_report.md` |
| Historical seasonal/burst | `results/results.md`; `results/runs/` |
| Integrated live evidence | `results/live_trace_phase/results.md` |
| D1/D2 | `results/dataset_phase/offline_results.md`; `online_results.md` |
| NASA/Alibaba forecasting | `results/real_world_forecasting/RESULTS.md`; `REPRODUCE.md` |
| Raw-data acquisition/local retention | `data/README.md`; `docs/LOCAL_EVIDENCE_RETENTION.md` |
| Per-live-experiment reproduction | `results/live_trace_phase/*/REPRODUCE.md` |

Large licensed/raw datasets remain local and gitignored. Their legitimate source
URLs, retained subset rules, source hashes, and generated artifacts are documented
in the linked files. Accepted live evidence must not be overwritten merely to
refresh a report.

## Optional future work

On isolated hardware, add prospectively ordered or randomized accepted repeats
for on/off, growing, stepped, Alibaba-derived, and guarded chaotic without
changing acceptance rules. Native-time or less-compressed replays, per-request
backend identity, a predeclared SLA, controller retuning as a labelled ablation,
and multiple cluster nodes would strengthen inference. Exact-paper forecasting
or Gemini reproduction would broaden scope but is not mandatory for this handoff.
