# Initial reproduction report

## Paper
- Title: From Reactive to Predictive: A Pattern-Aware Framework for Kubernetes Autoscaling with Large Language Model Integration
- Authors: Canberk Duman, Süleyman Eken
- Venue: Journal of Systems and Software, vol. 237, 2026
- DOI: https://doi.org/10.1016/j.jss.2026.112861
- GitHub (experiment harness): https://github.com/syswe/workloads-predictional-scaling-operators
- Kaggle (online pattern results): https://www.kaggle.com/datasets/cnbrkdmn/workloads-predictional-scaling-patterns
- Operator actually used: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`

## Problem being addressed
Kubernetes HPA adds pods only after CPU is already high. The paper adds predictive autoscaling (PHPA) with pattern-aware forecasting and LLM-based pattern recognition.

## Core method we implemented
The original live phase did **not** re-run the LLM classifier or all 42 online scenarios. The dataset phase now evaluates all 600 supplied synthetic scenarios under our own documented forecast protocol and audits all 42 released online traces. The original live phase ran the **online core**: `php-apache` (CPU request 200m), busybox load generator, metrics-server, the authors’ HPA settings (CPU target 50%, scale-down stabilization 60s, max 20), and Holt–Winters with the paper’s coefficients (α=0.9, β=0.2, γ=0.3, seasonalPeriods 6, syncPeriod 10s).

## Cloud computing component
Kubernetes schedules pods. HPA / PHPA change php-apache replicas. metrics-server is the metric pipeline. Docker Desktop Kubernetes (kind, 1 node, v1.36.1). No commercial cloud account.

## Multimodal component
None in our runs. The paper’s LLM path is multimodal text analysis of workloads; we did not call Gemini.

## Datasets (paper inventory + what we used)

Assignment step 3 requires documenting **all** datasets used in the selected paper. Below is the full inventory. D1 is now evaluated offline, D2 is independently analysed from released traces, and D5 contains our own cluster runs. These are distinct evidence sources.

### D1 — Synthetic pattern CSVs — evaluated offline

| Field | Detail |
|---|---|
| Name | PHPA Research Datasets — k8s Workload Patterns |
| Source | https://www.kaggle.com/datasets/cnbrkdmn/phpa-research-datasets |
| Samples | Measured: 1,200 CSV files, 600 paired scenarios, 2,016,000 observations (the supplied README’s ≈500,000 estimate is incorrect) |
| Modality | Univariate time series (`timestamp`, `pod_count`) |
| Characteristics | Six pattern families: Stepped, Burst, Seasonal, Growing, OnOff, Chaotic; 100 scenarios each; every combined train/test series spans 35 days at 15-minute sampling. Filename parameters describe the generator, not the observed file duration. |
| Train / val / test | Per scenario: **train** 2,688 rows and **test** 672 rows; verified contiguous 15-minute sampling |
| Preprocessing | Generated from mathematical pattern formulations (not raw production logs) |
| Filtering / augmentation | Parameter sweeps over pattern knobs; no image/audio augmentation |
| Multimodal combine | N/A (scalar pod_count series) |
| Used in paper for | Temporal cross-validation, pattern-adaptive model selection, +37.4% accuracy claim |
| **Used by us?** | **Yes** — all 600 scenarios, five forecast variants, 15/60-minute rolling horizons; a separate protocol, not an exact replication of the paper |

### D2 — Online Kubernetes pattern traces (authors’ released results)

| Field | Detail |
|---|---|
| Name | Workloads Predictional Scaling Patterns (PHPA online benchmark) |
| Source | https://www.kaggle.com/datasets/cnbrkdmn/workloads-predictional-scaling-patterns · harness https://github.com/syswe/workloads-predictional-scaling-operators |
| Samples | 42 online scenarios = 6 patterns × 7 strategies (HPA + 6 PHPA models); CSVs with ~5 s sampling |
| Modality | Cluster metrics time series: desired/current/ready replicas, CPU millicores, scale events |
| Characteristics | Load generator drives CPU on `php-apache` using the six pattern functions |
| Train / val / test | Not a supervised split; online control loop with warmup then collection |
| Preprocessing | Environment reset between scenarios; metrics via metrics-server |
| Filtering / augmentation | None beyond pattern schedule |
| Multimodal combine | N/A |
| Used in paper for | Early-detection vs HPA (e.g. Holt–Winters seasonal **30.8 s**, burst **20.5 s** earlier) |
| **Used by us?** | **Yes, released-data analysis** of all 42 traces plus 36 timing summaries. Separate newer local replays cover growing, on/off, stepped, and a safety-stopped chaotic attempt; these are not repetitions of the released D2 runs. |

### D3 — NASA HTTP logs — production-derived live replay

| Field | Detail |
|---|---|
| Name | NASA-HTTP (Kennedy Space Center WWW server) |
| Source | Internet Traffic Archive: https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html (Arlitt & Williamson) |
| Samples | Two months of HTTP requests (Jul 1995; Aug 1995 segment); on the order of **millions** of requests (ITA: ~3.46M in a documented two-week Aug window alone; full dumps are hundreds of MB uncompressed) |
| Modality | Text HTTP access logs (host, timestamp, request, status, bytes) — aggregated by the paper into a request-rate / load series for forecasting |
| Characteristics | Public web workload with diurnal and burst behaviour; 1 s timestamp resolution |
| Train / val / test | Paper uses for **generalisation / MAPE** of forecasting models (exact split not fully specified in the abstract; treated as production validation) |
| Preprocessing (typical for this use) | Parse CLF-style logs → aggregate requests into fixed time bins → optional smoothing before MAPE |
| Filtering / augmentation | Hurricane Erin gap in early Aug 1995 (server down) noted by ITA |
| Multimodal combine | N/A (log text → univariate rate series) |
| Used in paper for | Sub-2% MAPE claim for gradient boosting on production-style workloads |
| **Used by us?** | **Yes, live demand replay** — one fixed July window; 8/9 accepted controller matrix, not the paper's forecast-MAPE protocol |

### D4 — Alibaba Cluster Trace — bounded production-derived live replay

| Field | Detail |
|---|---|
| Name | Alibaba Cluster Trace (cluster / production resource trace used in the paper’s validation) |
| Source | Alibaba Cluster Trace Program (public cluster traces; commonly cited as Alibaba cluster-trace-* releases, e.g. https://github.com/alibaba/clusterdata) |
| Samples | Large-scale production cluster records (machines, batches, containers); paper uses a derived load/utilisation series for forecasting MAPE (exact subset size not stated in the abstract) |
| Modality | Structured cluster telemetry (CPU/memory/job events) → univariate forecasting target after aggregation |
| Characteristics | Real cloud multi-tenant noise; less regular than synthetic sine/burst patterns |
| Train / val / test | Used as **external validation** alongside NASA in the paper |
| Preprocessing | Trace parsing + aggregation to the forecasting horizon used by their models |
| Filtering / augmentation | Paper-specific filtering not fully detailed in open abstract snippets |
| Multimodal combine | N/A |
| Used in paper for | Sub-2% MAPE generalisation claim with gradient boosting |
| **Used by us?** | **Yes, with severe limitations** — first 42 `c_1` observations from a 16 MiB nonrepresentative archive prefix, transformed into HTTP demand; one accepted run per controller |

### D5 — Synthetic online load we executed — **USED BY US**

| Field | Detail |
|---|---|
| Name | `seasonal_pattern` and `burst_pattern` in `scripts/generate_pattern_load.py` (upstream harness) |
| Source | https://github.com/syswe/workloads-predictional-scaling-operators (same functions as D2) |
| Samples | Per run: ~17–21 metric rows over ~115–120 s wall time after 30 s warmup; 3 repeats × 2 patterns × 3 controllers = **18 CSVs** in `results/runs/` |
| Modality | HTTP load → CPU pressure on `php-apache`; recorded replica/CPU time series |
| Characteristics | **seasonal**: sine, base 4, amplitude 12, period ≈80 s, ~4–16 load-generator replicas. **burst**: base 4, peaks toward 18 at t≈30,100,180,260 s, duration ≈25 s. Deterministic (no RNG). |
| Train / val / test | None; Holt–Winters updates online inside the operator; state cleared between arms |
| Preprocessing | None beyond authors’ collector; pod-seconds via trapezoid on `elapsed_seconds` |
| Filtering / augmentation | None |
| Multimodal combine | N/A |
| How modalities combine | Single CPU metric drives HPA/PHPA |

### Dataset summary for graders

| Dataset | In paper? | In our experiments? |
|---|---|---|
| Kaggle synthetic train/test CSVs (D1) | Yes (offline) | Yes, all 600 scenarios under our protocol |
| Online 6×7 harness / Kaggle results (D2) | Yes | All 42 released traces audited; own live runs remain 2 patterns |
| NASA-HTTP (D3) | Yes (MAPE) | Yes, fixed-window live demand replay; not MAPE reproduction |
| Alibaba Cluster Trace (D4) | Yes (MAPE) | Yes, one-container observation-sequence live replay; not full dataset |
| Seasonal + burst live load (D5) | Yes (subset of D2) | **Yes** |

## Environment
- Host: Windows 10 + WSL2 Ubuntu 24.04 (`Ubuntu2404`), Docker Desktop Engine ~29.x, ~8 GB / 8 CPUs to Docker
- Node: `desktop-control-plane`, Kubernetes v1.36.1, containerd 2.3.1
- Python 3.12.3; kubectl v1.37.1; Helm v3.22.0
- Settings: `RUN_DURATION=120`, `WARMUP_DURATION=30`, `SAMPLING_INTERVAL=5` (authors’ Makefile defaults 300 / 60)

## Original results vs reproduced results

Paper abstract / body emphasise forecast accuracy and LLM classification. Online early-detection numbers appear in the authors’ **Kaggle** release (not as pod-seconds in the abstract). Our primary reproduced metric is **pod-seconds** (capacity), mean ± SD over 3 repeats.

| Result | Original / published | Ours | Difference / comparability |
|---|---|---|---|
| HW early detection vs HPA, seasonal | **30.8 s** earlier (rounded Kaggle release) | **30.77 s**, recomputed from released traces | Difference from exact release: 0; not a new live replication |
| HW early detection vs HPA, burst | **20.5 s** earlier (rounded Kaggle) | **20.48 s**, recomputed from released traces | Difference from exact release: 0; not a new live replication |
| Gemini pattern classification | **96.7%** (paper abstract) | NOT MEASURED | No LLM API call |
| Pattern-specific vs single-model forecast accuracy | **+37.4%** (paper abstract) | NOT MEASURED | Our 600-scenario evaluation uses a different protocol; the paper’s improvement denominator and exact comparison are not replicated |
| Gradient boosting MAPE on NASA / Alibaba | **sub-2%** (paper abstract) | NOT MEASURED | Our live demand-replay protocol does not reproduce the paper's forecasting protocol |
| D1 rolling one-step MAE | not published in a directly matching table | burst 1.0375 persistence; chaotic 2.6700 persistence; growing 0.3659 persistence; on/off 5.5859 GBDT; seasonal 0.5326 GBDT; stepped 0.6099 persistence | Our protocol and metric; no paper difference computed |
| New live request error / successful-request p95 | not supported as matching paper metrics | Measured for bounded NASA-, Alibaba-, on/off-, growing-, stepped-, and partial chaotic replays | NOT COMPARABLE to forecast MAPE or released early-detection seconds; see `results/live_trace_phase/results.md` |
| seasonal pod-seconds, strawman HPA | not in abstract | **943.01 ± 94.07** | Our metric |
| seasonal pod-seconds, Holt–Winters | not in abstract | **766.80 ± 39.61** | Our metric |
| seasonal pod-seconds, tuned HPA 70% | N/A (our addition) | **583.25 ± 79.59** | Our metric |
| burst pod-seconds, strawman HPA | not in abstract | **1088.25 ± 274.75** | High variance |
| burst pod-seconds, Holt–Winters | not in abstract | **728.38 ± 46.49** | Our metric |
| burst pod-seconds, tuned HPA 70% | N/A (our addition) | **653.40 ± 24.74** | Our metric |

Full tables, paired differences, Cohen’s d: [`results/results.md`](../results/results.md).

## Possible explanations for differences
Online early-detection is now recomputed on the authors’ released traces; it remains unmeasured in our shorter live runs. Pod-seconds are our evaluation addition for the capacity gap question. Holt–Winters state starts empty each arm; `seasonalPeriods=6` implies a 60 s season vs ~80 s seasonal load period — cold-start / mismatch risk.

## Installation problems
1. `docker pull syswe/predictive-horizontal-pod-autoscaler:latest` failed (image not public). Installed `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2` via Helm; adapted CR to `jamiethompson.me/v1alpha1` with the same HW coefficients.
2. Docker CLI not integrated into `Ubuntu2404` WSL; images pulled from Windows; kubectl from WSL used Docker Desktop kubeconfig.
3. metrics-server needed an explicit host pull of `registry.k8s.io/metrics-server/metrics-server:v0.7.1`.

## Missing resources
syswe Docker Hub image and Gemini API (not used). Full Alibaba archive was intentionally not downloaded; the bounded prefix is retained locally.

## Code problems
`quick_test.sh` is interactive and does not write CSVs — unused. Wrapper uses `run_pattern_tests.sh`.

## Dataset problems
D1’s README understates total observations: actual count is 2,016,000, with 77,633 zero targets across train and test. D2 has 183 rows with ready replicas exceeding current replicas; these are flagged without altering raw data. Original live seasonal/burst inputs are deterministic.

## Computational limitations
Original live phase: 18 arms ≈ 70 minutes. Dataset phase: all 600 offline scenarios and all 42 authors’ traces. Later production-derived work used a healthy dedicated v1.32.2 kind cluster for the partial NASA matrix and one three-controller Alibaba comparison; it is not the original Docker Desktop environment.

## Deviations from the original experiment
- Historical live protocol: 2 patterns and 3 controllers. Later QoS-capable
  replays cover growing and on/off with complete single-run matrices, stepped
  with two accepted arms and one rejected arm, and chaotic with only one
  accepted arm before the host-safety stop. Offline/released-data analysis
  covers all six patterns.
- 120 s / 30 s warmup (not 300 / 60).
- jthomperoo operator instead of missing syswe image.
- No LLM and no NASA/Alibaba forecast-MAPE reproduction; later live work maps bounded production observations into benchmark HTTP demand.
- Primary metric: pod-seconds + hot fraction (cost/capacity), not early-detection or forecast MAPE.

## Dataset extension artifacts

See [offline results](../results/dataset_phase/offline_results.md), [online trace audit](../results/dataset_phase/online_results.md), and [dataset phase status](STATUS_DATASET_PHASE.md). File-level SHA-256 hashes, exact row counts, per-scenario metrics, paired comparisons, and package versions are committed under `results/dataset_phase/`. Raw data remain local under `data/`. Earlier live results are preserved.

### Independent source verification

Initial computations used the supplied ZIP. Subsequent direct Kaggle downloads matched all 1,288 supplied files byte-for-byte (1,201 D1 and 87 D2), including all 1,249 CSVs. Source URLs, archive hashes and per-file comparisons are recorded in `results/dataset_phase/kaggle_source_verification.json`. The independent output verifier and all three temporal/metric tests passed again. Source identity does not imply equivalence to the paper’s experimental protocol.
