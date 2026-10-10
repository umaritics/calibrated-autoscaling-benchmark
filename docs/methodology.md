# Methodology

## 1. Baseline from the referenced article

We use the online experiment of Duman and Eken (Journal of Systems and Software, 2026, https://doi.org/10.1016/j.jss.2026.112861) as the baseline system. The implementation starts from their repository `syswe/workloads-predictional-scaling-operators`. Because their advertised Docker image `syswe/predictive-horizontal-pod-autoscaler:latest` was not available on Docker Hub, the operator we deployed is the upstream image their own documentation points to: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`, installed with the official Helm chart into namespace `phpa-system`.

The cluster runs `php-apache` (CPU request 200 millicores, limit 500 millicores) and a busybox load generator. `scripts/generate_pattern_load.py` sets the load-generator replica count. `metrics-server` exposes CPU. Two original controllers are kept as the reproduction baseline:

- Strawman HPA, file `manifests/hpa-baseline.yaml` (unchanged): target average CPU utilization 50%, scale-up stabilization 0 seconds, scale-down stabilization 60 seconds, minimum 1 replica, maximum 20 replicas.
- Holt–Winters predictive autoscaler: alpha 0.9, beta 0.2, gamma 0.3, seasonalPeriods 6, storedSeasons 4, additive trend, additive season, sync period 10 seconds, CPU target 50%, minimum 1, maximum 20. The YAML API group is `jamiethompson.me/v1alpha1` to match the installed operator; the algorithm parameters match the paper’s published configuration.

We evaluate the seasonal pattern and the burst pattern. We do not re-implement their LLM classifier.

## 2. Research gap

The authors’ reactive baseline targets 50% CPU and can remove pods after 60 seconds. That baseline keeps spare pods and then sheds them quickly, so a forecaster’s gain is measured against a weak controller. The paper’s published headline numbers evaluate forecast accuracy and LLM classification. They do not answer when a tuned reactive controller is already enough, separately on a repeating pattern and on a spike pattern.

## 3. Proposed method

### Component A — calibrated HPA

New file `manifests/hpa-calibrated.yaml`. The authors’ baseline file is not modified. The calibrated object uses the same Kubernetes name `php-apache-baseline` so it can be applied only when the strawman object is absent.

- CPU target 70%.
- Scale-up stabilization 0 seconds, at most 4 pods per 60 seconds.
- Scale-down stabilization 300 seconds, and at most 50% of pods per 60 seconds.

A 70% target leaves fewer idle pods than 50%. A 300-second scale-down window matches Kubernetes’ default stabilization and avoids deleting pods during a short dip. The 4-pod cap avoids a jump toward the maximum of 20 on a single spike.

### Component B — pattern switch

No new forecasting model. The experiment already knows the pattern name because that name is passed to the load generator. This is not online classification.

- seasonal: run Holt–Winters.
- burst: run the reactive HPA.

Component B alone uses the strawman HPA on burst. Components A and B together use the calibrated HPA on burst. Seasonal always uses Holt–Winters. These two derived conditions reuse the CSVs of the arm they select. They are not extra cluster runs.

## 4. Experimental protocol

- Namespace `phpa-lab`. Operator namespace `phpa-system`.
- Collection 120 seconds, warmup 30 seconds, sample every 5 seconds.
- Three repeats. The authors’ script deletes the autoscaler and resets php-apache to 1 replica between arms.
- Controllers are never applied together.
- Cluster: Docker Desktop kind node `desktop-control-plane`, Kubernetes v1.36.1, one control-plane node.

## 5. Metrics

Collected columns are the authors’ collector columns: desired, current, and ready replicas, and CPU millicores. We report mean ready replicas, max ready replicas, pod-seconds, mean per-pod CPU, the number of changes in desired replicas, the first time ready replicas reach 2, and the fraction of samples whose average pod CPU exceeds 160 millicores (80% of the 200 millicore request).

Pod-seconds stand in for capacity used. The hot fraction stands in for saturation. The harness does not record latency, so we do not report an SLA.

Advantage of Holt–Winters against a reactive controller is `pod_seconds(reactive) - pod_seconds(Holt–Winters)`. The calibration gap is the advantage against the strawman minus the advantage against the calibrated HPA.

## 6. Results

Copied from `output/our_study/results.md` after 18 successful cluster runs (3 repeats × 2 patterns × 3 measured arms).

### Mean across repeats

| Pattern | Arm | Repeats found | Mean pod-seconds | Mean hot fraction | Mean desired-replica changes |
|---|---|---:|---:|---:|---:|
| seasonal | strawman_hpa | 3 | 978.92 | 0.850 | 4.67 |
| seasonal | holtwinters | 3 | 800.11 | 0.865 | 2.67 |
| seasonal | calibrated_hpa | 3 | 608.54 | 0.951 | 5.00 |
| burst | strawman_hpa | 3 | 1122.98 | 0.554 | 4.00 |
| burst | holtwinters | 3 | 735.51 | 0.699 | 3.00 |
| burst | calibrated_hpa | 3 | 668.09 | 0.806 | 4.67 |

### Derived arms (no extra cluster run)

| Pattern | Derived arm | Selected measured arm | Mean pod-seconds | Mean hot fraction |
|---|---|---|---:|---:|
| seasonal | B_switch_strawman | holtwinters | 800.11 | 0.865 |
| burst | B_switch_strawman | strawman_hpa | 1122.98 | 0.554 |
| seasonal | AB_switch_calibrated | holtwinters | 800.11 | 0.865 |
| burst | AB_switch_calibrated | calibrated_hpa | 668.09 | 0.806 |

### Calibration gap

| Pattern | Mean pod-seconds strawman | Mean pod-seconds Holt–Winters | Mean pod-seconds calibrated | Advantage vs strawman | Advantage vs calibrated | Calibration gap |
|---|---:|---:|---:|---:|---:|---:|
| seasonal | 978.92 | 800.11 | 608.54 | 178.81 | -191.57 | 370.38 |
| burst | 1122.98 | 735.51 | 668.09 | 387.47 | -67.41 | 454.89 |

## 7. What the comparison shows

Against the authors’ 50% HPA, Holt–Winters uses fewer pod-seconds on both seasonal (+178.81) and burst (+387.47). Against the calibrated 70% HPA, that advantage reverses: calibrated HPA uses fewer pod-seconds than Holt–Winters on both patterns (−191.57 seasonal, −67.41 burst). The calibration gaps are large and positive (370.38 seasonal, 454.89 burst), which means most of the predictive “win” existed only because the reactive baseline was weakly tuned. The calibrated arm also shows a higher hot fraction, so pods are busier rather than idle. We do not claim a latency improvement; the harness does not record request latency.

## 8. Threats to validity

- The window is 120 seconds, shorter than the authors’ 300-second default.
- Docker Desktop on one laptop is not the authors’ cluster.
- The pattern name is given to Component B. A deployed system would still need a classifier. We did not evaluate one.
- Pod-seconds and the hot fraction are proxies. They are not the paper’s MAPE and not a user-facing SLA.
- Repeats share one machine. Background load on the laptop can move CPU.
- The operator binary is the upstream jthomperoo release, not a private syswe image, because that image was not pullable.

## 9. Ablation map required by the course

| System | seasonal controller | burst controller | Where the number comes from |
|---|---|---|---|
| Original paper system | strawman HPA, compared with always-on Holt–Winters | strawman HPA, compared with always-on Holt–Winters | measured arms strawman_hpa and holtwinters |
| Original + Component A | calibrated HPA, compared with always-on Holt–Winters | calibrated HPA, compared with always-on Holt–Winters | measured arms calibrated_hpa and holtwinters |
| Original + Component B | Holt–Winters | strawman HPA | derived arm B_switch_strawman |
| Original + A + B | Holt–Winters | calibrated HPA | derived arm AB_switch_calibrated |
