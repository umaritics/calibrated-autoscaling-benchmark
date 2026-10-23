# Methodology

## 1. Baseline from the referenced article

We use the online experiment of Duman and Eken (Journal of Systems and Software, 2026, https://doi.org/10.1016/j.jss.2026.112861) as the baseline system. The implementation starts from their repository `syswe/workloads-predictional-scaling-operators`. Because their advertised Docker image `syswe/predictive-horizontal-pod-autoscaler:latest` was not available on Docker Hub, the operator we deployed is the upstream image their documentation points to: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`.

The cluster runs `php-apache` (CPU request 200 millicores, limit 500 millicores) and a busybox load generator. `scripts/generate_pattern_load.py` sets the load-generator replica count. `metrics-server` exposes CPU. Two original controllers are kept as the reproduction baseline:

- Strawman HPA, file `policies/hpa-baseline.yaml` (unchanged): target average CPU utilization 50%, scale-up stabilization 0 seconds, scale-down stabilization 60 seconds, minimum 1 replica, maximum 20 replicas.
- Holt–Winters predictive autoscaler: alpha 0.9, beta 0.2, gamma 0.3, seasonalPeriods 6, storedSeasons 4, additive trend, additive season, sync period 10 seconds, CPU target 50%, minimum 1, maximum 20. The YAML API group is `jamiethompson.me/v1alpha1` to match the installed operator; the algorithm parameters match the authors’ published configuration.

The original live experiments evaluated seasonal and burst. Later bounded work
added NASA-, Alibaba-, on/off-, growing-, stepped-, and chaotic-derived demand
replays; see `results/live_trace_phase/results.md`. Those later runs use a
different QoS-capable harness and are not pooled with this historical protocol.
We do not re-implement the paper's LLM classifier (Gemini 2.5 Pro, reported
96.7% pattern-classification accuracy) or its exact offline protocol (+37.4%
accuracy; sub-2% MAPE on NASA/Alibaba). The dataset extension evaluates the
supplied synthetic scenarios independently. NASA/Alibaba HTTP replays are not
forecast-MAPE reproduction.

Full documentation of every dataset in the paper (synthetic Kaggle CSVs, online harness traces, NASA-HTTP, Alibaba Cluster Trace) and which ones we executed is in [`docs/reproduction_report.md`](reproduction_report.md) § Datasets.

## 2. Research gap

The authors’ reactive baseline targets 50% CPU and can remove pods after 60 seconds. That baseline holds spare capacity, so a forecaster’s capacity advantage can look large against a soft controller. The paper’s published headline numbers evaluate forecast accuracy, LLM classification, and (in their Kaggle online release) early-detection time versus HPA. They do not answer when a more conservatively tuned reactive controller is already competitive on capacity, separately on a repeating pattern and on a spike pattern.

## 3. Proposed method

### Component A — conservatively tuned HPA

New file `policies/hpa-calibrated.yaml` (filename kept for continuity; meaning: **one documented conservative tune**, not a multi-value calibration sweep). The authors’ baseline file is not modified.

- CPU target 70%.
- Scale-up stabilization 0 seconds, at most 4 pods per 60 seconds.
- Scale-down stabilization 300 seconds, and at most 50% of pods per 60 seconds.

A 70% target leaves fewer idle pods than 50%. A 300-second scale-down window matches Kubernetes’ default stabilization. The 4-pod cap avoids a jump toward the maximum of 20 on a single spike.

### Component B — pattern switch

No new forecasting model. The experiment already knows the pattern name because that name is passed to the load generator. This is not online classification.

- seasonal: run Holt–Winters.
- burst: run the reactive HPA.

Component B alone uses the strawman HPA on burst. Components A and B together use the tuned HPA on burst. Seasonal always uses Holt–Winters. These derived conditions reuse CSVs; they are not extra cluster runs.

## 4. Experimental protocol

- Namespace `phpa-lab`. Operator namespace `phpa-system`.
- Collection 120 seconds, warmup 30 seconds, sample every 5 seconds (authors’ defaults: 300 s / 60 s).
- Three repeats. Controllers are never applied together.
- Cluster: Docker Desktop kind node `desktop-control-plane`, Kubernetes v1.36.1.

## 5. Metrics

Collected columns are the authors’ collector columns: desired, current, and ready replicas, and CPU millicores. We report pod-seconds (trapezoidal integral of ready replicas over `elapsed_seconds`), hot fraction (share of samples with average pod CPU > 160 m = 80% of the 200 m request), mean CPU, and scaling churn.

**Holt–Winters capacity advantage** against a reactive controller:

`advantage = pod_seconds(reactive) − pod_seconds(Holt–Winters)`

Positive ⇒ Holt–Winters held less capacity. We do **not** report “calibration gap = advantage(strawman) − advantage(tuned)”, because that expression cancels Holt–Winters and equals strawman − tuned.

The harness does not record request latency, so we make **no SLA / performance claim**.

## 6. Results

See [`results/results.md`](../results/results.md) for full per-run tables, mean ± SD (n=3), paired differences, and Cohen’s d.

### Summary (pod-seconds, mean ± SD)

| Pattern | Strawman HPA | Holt–Winters | Tuned HPA (70%) | HW adv. vs strawman | HW adv. vs tuned |
|---|---:|---:|---:|---:|---:|
| seasonal | 943.01 ± 94.07 | 766.80 ± 39.61 | 583.25 ± 79.59 | 176.21 ± 92.44 | −183.55 ± 41.69 |
| burst | 1088.25 ± 274.75 | 728.38 ± 46.49 | 653.40 ± 24.74 | 359.86 ± 264.76 | −74.98 ± 62.29 |

Hot fraction (mean ± SD): seasonal strawman 0.850 ± 0.089, HW 0.865 ± 0.056, tuned 0.951 ± 0.050; burst strawman 0.554 ± 0.096, HW 0.699 ± 0.133, tuned 0.806 ± 0.086.

Cohen’s d on pod-seconds (strawman vs HW): seasonal 2.44, burst 1.83. Tuned vs HW: seasonal −2.92, burst −2.01 (negative ⇒ tuned lower capacity).

Authors’ published online early-detection (Kaggle release, HW vs HPA): seasonal **30.8 s**, burst **20.5 s** earlier. Not re-measured in our shortened windows.

## 7. What the comparison shows

This is a **cost/capacity** comparison (pod-seconds), not a latency or SLA evaluation.

- Against the authors’ **50% HPA**, Holt–Winters uses fewer pod-seconds on both patterns (positive advantage; large effect size on seasonal).
- Against the **70% conservatively tuned HPA**, that capacity advantage **reverses**: the tuned reactive controller uses fewer pod-seconds than Holt–Winters on seasonal in all three repeats (paired mean −183.55 ± 41.69). On burst the tuned arm is also lower on average (−74.98 ± 62.29), but repeats overlap and variance is high — treat burst as suggestive, not definitive.
- The tuned arm has the **highest hot fraction** and mean per-pod CPU above the 200 m request. Fewer pods therefore come with heavier per-pod load. Without latency, we do **not** claim better user-facing performance — only that a soft 50% baseline inflates how good prediction looks on capacity.

## 8. Threats to validity

- Window 120 s (authors often use 300 s); burst peaks at 30/100/180/260 s ⇒ at most ~1–2 bursts in our window.
- Holt–Winters `seasonalPeriods: 6` at 10 s sync ⇒ 60 s season, while the seasonal load period is ~80 s; state is cleared between arms (cold start risk).
- Row counts 17–21 vs nominal 24; pod-seconds use timestamps (trapezoid), not row×5.
- Docker Desktop laptop ≠ authors’ cluster.
- Pattern label given to Component B; no LLM classifier evaluated.
- One tuned HPA config, not a hyperparameter sweep.
- No latency/SLA metric.

## 9. Ablation map required by the course

| System | seasonal controller | burst controller | Where the number comes from |
|---|---|---|---|
| Original paper system | strawman HPA vs always-on Holt–Winters | strawman HPA vs always-on Holt–Winters | measured strawman_hpa, holtwinters |
| Original + Component A | tuned HPA vs always-on Holt–Winters | tuned HPA vs always-on Holt–Winters | measured calibrated_hpa, holtwinters |
| Original + Component B | Holt–Winters | strawman HPA | derived B_switch_strawman |
| Original + A + B | Holt–Winters | tuned HPA | derived AB_switch_tuned |

## 10. Dataset extension protocol

All 600 D1 scenarios (100 each of burst, chaotic, growing, onoff, seasonal, stepped) are used. Each supplied chronological split has 2,688 training and 672 test samples at 15-minute intervals. The pipeline rejects missing pairs, invalid targets, or noncontiguous timestamps rather than silently dropping them. A file manifest records SHA-256, byte size, row count, and zero targets.

Forecast horizons are 1 and 4 samples (15 and 60 minutes). Forecast origins begin after all training observations are available. Hence horizon 4 scores test indices 3–671 (669 targets); horizon 1 scores all 672. Models see only observations preceding each origin, including earlier test observations as they arrive. This is rolling-origin forecasting, not a fixed-origin forecast of the entire test block.

Five variants are compared: persistence, trailing six-sample mean, additive Holt–Winters with period 6, Holt–Winters with period selected on the final 20% of training data, and histogram gradient boosting with 24 lag features. HW uses alpha .9, beta .2, gamma .3; candidate periods are 6/12/24/48/96. Period selection minimizes validation MAE separately for each scenario and horizon. Initialization uses two training seasons. GBDT uses 60 iterations, 15 leaves, learning rate .1, seed 0, no early stopping; it fits direct horizon-specific targets once on training data. Negative forecasts are clipped to zero. Neither filenames nor known pattern labels are model features. Period 6 is a sensitivity baseline, not a claim that six offline samples correspond to the live 60-second season.

MAE/RMSE include zero-demand observations. MAPE is explicitly nonzero-only; WAPE uses the sum of absolute targets. Results macro-average scenario metrics, with SD across scenarios (not repeated runs). Paired MAE differences and win counts use the same scenarios. No test-driven hyperparameter search or claim of statistical significance is made. Forecast accuracy alone cannot establish the tuned HPA’s cost or QoS performance on the four additional patterns.

D2 analysis integrates the released ready-replica column over actual elapsed timestamps and reports duration-normalized capacity, saturation, and inconsistent ready/current counts. Timing uses first observed desired-replica increases; ready-replica timing is separate. Released summaries remain identifiable as author-reported values. These are independent runs with warmup and differing windows, not paired repetitions. No synthetic tuned-HPA outcome is inferred from them.

Reproduce with `python scripts/evaluate_datasets.py`; see `requirements-datasets.txt` and `results/dataset_phase/environment.json`. Tests in `tests/test_dataset_evaluation.py` check future-data isolation, horizon alignment, constant-series HW behavior, and zero handling.

## 11. Real-world forecast-accuracy protocol

Task 11 is separate from every live controller run. NASA uses the raw July 1995
HTTP log, fixed UTC−04:00 timestamps, complete five-minute calendar bins, and
request count as the target. The incomplete trailing bin is excluded; covered
bins without requests remain zero. Alibaba uses the raw v2018 container-usage
prefix and `cpu_util_percent`. Individual containers are too sparse for honest
native-cadence forecasting, so the deterministic target is the arithmetic mean
of valid observations from completed named container blocks at each exact
timestamp. The selected window is the earliest longest exact 10-second run
having at least 20 contributors at every timestamp. The boundary-truncated
container is excluded; no missing observation becomes zero or is imputed.

Each dataset uses a chronological 60/20/20 train/validation/test split and
rolling origins. Horizons are 5 and 60 minutes for NASA and 10 and 60 seconds
for Alibaba. Models are persistence, trailing moving average, validation-tuned
exponential smoothing, and fixed-hyperparameter histogram GBDT with past-target
lags only. NASA smoothing has a fixed daily season; Alibaba uses nonseasonal
Holt linear smoothing because the retained 9.7-hour window cannot establish a
season. MAPE excludes and counts zero actuals explicitly; MAE, RMSE, WAPE, and
sMAPE include every forecast pair. Exact boundaries, parameters, and rules are
frozen in `results/real_world_forecasting/evaluation_protocol.json`.

Forecast accuracy does not imply improved pod-seconds, service quality, or
scale timing. NASA request counts and Alibaba CPU percentages are never pooled.
