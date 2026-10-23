# Measured results

Every figure below was computed from a CSV under `results/runs`. Missing runs are `NOT MEASURED`. No latency or SLA column exists because the collector does not record requests.

## Sampling note

Collection was requested for 120 s at a 5 s interval (≈24 samples). Observed row counts are 17–21 because `kubectl`/metrics polling occasionally skips a cycle under load. **Pod-seconds use trapezoidal integration over `elapsed_seconds` timestamps**, not `rows × 5`.

## Naming

`calibrated_hpa` is a **conservatively tuned** reactive baseline (CPU target 70%, scale-down stabilization 300 s, max +4 pods/min). It is one documented configuration, not a multi-value sweep.

## Per run

| Repeat | Pattern | Arm | Rows | Duration (s) | Mean ready | Max ready | Pod-seconds | Mean CPU m | Desired changes | First ready≥2 (s) | Hot fraction |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| repeat1 | seasonal | strawman_hpa | 19 | 119.0 | 7.26 | 20 | 849.79 | 258.91 | 5 | 31.0 | 0.789 |
| repeat1 | seasonal | holtwinters | 19 | 118.0 | 6.53 | 10 | 779.66 | 268.88 | 3 | 6.6 | 0.895 |
| repeat1 | seasonal | calibrated_hpa | 19 | 115.1 | 5.05 | 8 | 590.07 | 302.68 | 6 | 11.9 | 1.000 |
| repeat1 | burst | strawman_hpa | 18 | 113.4 | 12.06 | 20 | 1396.97 | 174.73 | 3 | 12.7 | 0.444 |
| repeat1 | burst | holtwinters | 17 | 119.9 | 6.06 | 10 | 755.64 | 233.06 | 2 | 18.3 | 0.647 |
| repeat1 | burst | calibrated_hpa | 20 | 116.9 | 5.70 | 9 | 667.99 | 238.96 | 4 | 0.0 | 0.750 |
| repeat2 | seasonal | strawman_hpa | 21 | 118.7 | 8.67 | 20 | 1037.91 | 259.14 | 5 | 11.1 | 0.952 |
| repeat2 | seasonal | holtwinters | 20 | 119.1 | 6.55 | 10 | 798.38 | 264.13 | 3 | 6.3 | 0.900 |
| repeat2 | seasonal | calibrated_hpa | 20 | 119.7 | 5.45 | 9 | 659.22 | 316.93 | 4 | 12.0 | 0.900 |
| repeat2 | burst | strawman_hpa | 21 | 117.5 | 7.38 | 18 | 870.60 | 242.07 | 4 | 28.3 | 0.619 |
| repeat2 | burst | holtwinters | 20 | 117.0 | 6.35 | 10 | 754.81 | 231.96 | 3 | 5.7 | 0.600 |
| repeat2 | burst | calibrated_hpa | 21 | 118.6 | 5.14 | 9 | 624.84 | 262.93 | 6 | 11.6 | 0.905 |
| repeat3 | seasonal | strawman_hpa | 21 | 119.0 | 7.76 | 20 | 941.32 | 286.14 | 4 | 27.7 | 0.810 |
| repeat3 | seasonal | holtwinters | 20 | 116.0 | 6.15 | 10 | 722.36 | 257.32 | 2 | 17.8 | 0.800 |
| repeat3 | seasonal | calibrated_hpa | 21 | 116.5 | 4.24 | 8 | 500.47 | 313.54 | 5 | 27.9 | 0.952 |
| repeat3 | burst | strawman_hpa | 20 | 114.3 | 8.60 | 16 | 997.17 | 218.57 | 5 | 12.4 | 0.600 |
| repeat3 | burst | holtwinters | 20 | 116.9 | 5.65 | 10 | 674.71 | 249.33 | 4 | 16.9 | 0.850 |
| repeat3 | burst | calibrated_hpa | 21 | 118.8 | 5.52 | 9 | 667.38 | 270.91 | 4 | 11.6 | 0.762 |

## Mean ± SD across repeats (n=3)

| Pattern | Arm | Pod-seconds (mean ± SD) | Hot fraction (mean ± SD) | Mean desired-replica changes |
|---|---|---:|---:|---:|
| seasonal | strawman_hpa | 943.01 ± 94.07 | 0.850 ± 0.089 | 4.67 |
| seasonal | holtwinters | 766.80 ± 39.61 | 0.865 ± 0.056 | 2.67 |
| seasonal | calibrated_hpa | 583.25 ± 79.59 | 0.951 ± 0.050 | 5.00 |
| burst | strawman_hpa | 1088.25 ± 274.75 | 0.554 ± 0.096 | 4.00 |
| burst | holtwinters | 728.38 ± 46.49 | 0.699 ± 0.133 | 3.00 |
| burst | calibrated_hpa | 653.40 ± 24.74 | 0.806 ± 0.086 | 4.67 |

## Per-repeat paired differences (pod-seconds)

Positive means the first arm used **more** pod-seconds (worse on capacity).

| Pattern | Comparison | repeat1 | repeat2 | repeat3 | mean ± SD |
|---|---|---:|---:|---:|---:|
| seasonal | strawman_hpa − holtwinters | 70.13 | 239.54 | 218.96 | 176.21 ± 92.44 |
| seasonal | calibrated_hpa − holtwinters | -189.59 | -139.16 | -221.88 | -183.55 ± 41.69 |
| seasonal | strawman_hpa − calibrated_hpa | 259.72 | 378.70 | 440.85 | 359.75 ± 92.04 |
| burst | strawman_hpa − holtwinters | 641.34 | 115.79 | 322.46 | 359.86 ± 264.76 |
| burst | calibrated_hpa − holtwinters | -87.65 | -129.97 | -7.33 | -74.98 ± 62.29 |
| burst | strawman_hpa − calibrated_hpa | 728.99 | 245.76 | 329.79 | 434.85 ± 258.18 |

## Holt–Winters advantage (capacity)

`advantage = pod_seconds(reactive) − pod_seconds(holtwinters)`. Positive ⇒ Holt–Winters used fewer pod-seconds than that reactive controller. We **do not** report a “calibration gap” of the form advantage(strawman) − advantage(calibrated), because that expression algebraically cancels Holt–Winters and equals strawman − calibrated.

| Pattern | Strawman pod-s | HW pod-s | Tuned HPA pod-s | HW adv. vs strawman | HW adv. vs tuned HPA | Cohen's d (strawman − HW) | Cohen's d (tuned − HW) |
|---|---:|---:|---:|---:|---:|---:|---:|
| seasonal | 943.01 ± 94.07 | 766.80 ± 39.61 | 583.25 ± 79.59 | 176.21 ± 92.44 | -183.55 ± 41.69 | 2.44 | -2.92 |
| burst | 1088.25 ± 274.75 | 728.38 ± 46.49 | 653.40 ± 24.74 | 359.86 ± 264.76 | -74.98 ± 62.29 | 1.83 | -2.01 |

## Derived arms (no extra cluster run)

Component B uses Holt–Winters on seasonal and strawman HPA on burst. Components A+B use Holt–Winters on seasonal and conservatively tuned HPA on burst.

| Pattern | Derived arm | Selected measured arm | Pod-seconds (mean ± SD) | Hot fraction (mean ± SD) |
|---|---|---|---:|---:|
| seasonal | B_switch_strawman | holtwinters | 766.80 ± 39.61 | 0.865 ± 0.056 |
| burst | B_switch_strawman | strawman_hpa | 1088.25 ± 274.75 | 0.554 ± 0.096 |
| seasonal | AB_switch_tuned | holtwinters | 766.80 ± 39.61 | 0.865 ± 0.056 |
| burst | AB_switch_tuned | calibrated_hpa | 653.40 ± 24.74 | 0.806 ± 0.086 |

## Cost vs saturation (read together)

Lower pod-seconds mean less capacity held. Higher hot fraction / mean CPU above the 200 m request mean pods are busier. The conservatively tuned HPA often wins on pod-seconds **and** shows higher saturation. Without latency, that is a **cost/capacity** finding only, not a service-quality claim.

## Paper online numbers we can cite (early detection)

Authors’ Kaggle online release reports Holt–Winters early-detection vs HPA (seconds earlier): seasonal **30.8 s**, burst **20.5 s**. We did not recompute early-detection in our shortened 120 s windows; our primary metric is pod-seconds.

## Files read

- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\seasonal\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\seasonal\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\seasonal\calibrated_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\burst\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\burst\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat1\burst\calibrated_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\seasonal\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\seasonal\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\seasonal\calibrated_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\burst\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\burst\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat2\burst\calibrated_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\seasonal\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\seasonal\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\seasonal\calibrated_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\burst\strawman_hpa.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\burst\holtwinters.csv`
- ok: `U:\University\Semester 7\Cloud\Research\_repo_clean\results\runs\repeat3\burst\calibrated_hpa.csv`

## Dataset phase extension (separate evidence)

The live tables above remain unchanged. New [offline results](dataset_phase/offline_results.md) cover all 600 supplied scenarios across six patterns, five forecast variants, and two horizons. [Released online trace analysis](dataset_phase/online_results.md) audits all 42 authors’ traces and 36 early-detection summaries. Per-scenario values, manifests, package versions and full model tables are under `results/dataset_phase/`.

These analyses extend pattern coverage without treating authors' released runs
as extra repetitions of our local study. Subsequent QoS-capable live replays
exist for NASA, Alibaba-derived, growing, on/off, stepped, and a safety-stopped
chaotic attempt; they use a different protocol and remain consolidated in
[the live report](live_trace_phase/results.md). See the
[phase status](../docs/STATUS_DATASET_PHASE.md) for exact dispositions.

### Lowest mean MAE among the five evaluated variants

| pattern | horizon_steps | model | mae |
|---|---|---|---|
| burst | 1 | persistence | 1.0375 |
| burst | 4 | gbdt | 2.2975 |
| chaotic | 1 | persistence | 2.67 |
| chaotic | 4 | persistence | 4.1074 |
| growing | 1 | persistence | 0.3659 |
| growing | 4 | persistence | 0.6371 |
| onoff | 1 | gbdt | 5.5859 |
| onoff | 4 | gbdt | 7.6591 |
| seasonal | 1 | gbdt | 0.5326 |
| seasonal | 4 | gbdt | 0.6243 |
| stepped | 1 | persistence | 0.6099 |
| stepped | 4 | persistence | 0.9876 |

These are descriptive test-set rankings, not a deployed pattern-switch policy. At 15 minutes, persistence leads four of six patterns; GBDT leads seasonal and onoff. A forecasting gain is not a measured pod-second or latency gain. Full MAE/RMSE/MAPE/WAPE tables, scenario variability and paired wins are in the linked offline report.
