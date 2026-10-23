# Integrated cross-pattern research comparison

This report consolidates verified summary files without rerunning any workload.
Four evidence classes remain separate because their protocols and units differ:

1. historical live **capacity-only** seasonal/burst runs;
2. newer live **QoS + capacity** demand replays;
3. offline forecasting and authors' released-trace analysis; and
4. rejected, inconclusive, or interrupted supplementary evidence.

Raw pod-seconds are compared only within the same frozen workload and duration.
They are not averaged across different intensities, mappings, or time scales.

## New live QoS + capacity results

Error and timeout rates use all scheduled measurement requests. Latency p95 uses
successful requests only. `n` is the number of accepted repetitions contributing
to the row. `Changes` is desired-replica changes; NASA reports mean ± sample SD,
while single-run rows report the observed integer.

| Workload | Controller | n | Error | Timeout | Success p95 (s) | Pod-s | Pod-s / success | Changes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| NASA-derived | Soft HPA | 3 | 44.76% ± 9.37% | 44.64% ± 9.32% | 2.508 ± 0.918 | 1192.50 ± 156.12 | 0.08455 ± 0.02005 | 2.67 ± 0.58 |
| NASA-derived | Tuned HPA | 2 | 37.75% ± 2.34% | 37.64% ± 2.28% | 2.241 ± 0.306 | 915.00 ± 17.68 | 0.05633 ± 0.00103 | 3.00 ± 0.00 |
| NASA-derived | Holt–Winters | 3 | 18.04% ± 2.05% | 18.02% ± 2.06% | 0.868 ± 0.653 | 3479.17 ± 20.21 | 0.16271 ± 0.00498 | 3.67 ± 2.08 |
| Alibaba-derived | Soft HPA | 1 | 0.00% | 0.00% | 0.009 | 1277.50 | 0.08859 | 7 |
| Alibaba-derived | Tuned HPA | 1 | 0.00% | 0.00% | 0.008 | 1317.50 | 0.09137 | 3 |
| Alibaba-derived | Holt–Winters | 1 | 0.00% | 0.00% | 0.015 | 1422.50 | 0.09865 | 5 |
| On/off | Soft HPA | 1 | 50.05% | 49.99% | 1.456 | 1612.50 | 0.10785 | 7 |
| On/off | Tuned HPA | 1 | 48.55% | 48.46% | 1.069 | 1332.50 | 0.08654 | 3 |
| On/off | Holt–Winters | 1 | 13.29% | 13.20% | 0.050 | 3542.50 | 0.13651 | 8 |
| Growing | Soft HPA | 1 | 0.00% | 0.00% | 0.009 | 1927.50 | 0.06272 | 7 |
| Growing | Tuned HPA | 1 | 0.00% | 0.00% | 0.010 | 1572.50 | 0.05117 | 5 |
| Growing | Holt–Winters | 1 | 0.00% | 0.00% | 0.012 | 2897.50 | 0.09428 | 11 |
| Stepped | Tuned HPA | 1 | 17.58% | 17.54% | 0.011 | 5872.50 | 0.08424 | 6 |
| Stepped | Holt–Winters | 1 | 1.01% | 1.00% | 0.016 | 13025.00 | 0.15557 | 14 |
| Chaotic | Soft HPA | 1 | 85.47% | 85.07% | 4.482 | 685.00 | 0.14646 | 3 |
| Guarded chaotic 10–45 RPS | Tuned HPA | 1 | 0.00% | 0.00% | 0.011 | 990.00 | 0.07900 | 2 |
| Guarded chaotic 10–45 RPS | Holt–Winters | 1 | 0.00% | 0.00% | 0.012 | 1342.50 | 0.10713 | 5 |
| Guarded chaotic 10–45 RPS | Soft HPA | 1 | 0.00% | 0.00% | 0.012 | 1185.00 | 0.09456 | 1 |

Traceable sources: `nasa_three_repeat/mean_sd.csv`,
`alibaba_first_comparison/comparison.csv`,
`onoff_first_comparison/comparison.csv`,
`growing_first_comparison/comparison.csv`,
`stepped_first_comparison/comparison.csv`, and
`chaotic_first_comparison/safety_checkpoint.json`, and
`guarded_chaotic_comparison/comparison.csv`.

### Scaling behaviour

- **NASA:** Holt–Winters held roughly 8.28 mean ready replicas and delivered the
  best observed QoS, versus 2.84 soft and 2.18 tuned, at about 2.9× soft and 3.8×
  accepted tuned pod-seconds. Tuned improved error and capacity over soft in the
  two valid pairs, but its missing third accepted run makes that aggregate
  selection-biased toward telemetry-complete executions.
- **Alibaba-derived:** all requests succeeded. Soft used the least capacity;
  tuned was +3.13% and Holt–Winters +11.35% in pod-seconds. There was no observed
  QoS reason to pay the predictor's extra capacity in this one transformed run.
- **On/off:** Holt–Winters reduced errors by 35.26 percentage points versus tuned
  but used 165.9% more pod-seconds. Tuned saved 17.4% capacity versus soft but did
  not materially avoid overload. None of the transition metrics proves advance
  prediction.
- **Growing:** all requests succeeded. Tuned used 18.42% fewer pod-seconds than
  soft; Holt–Winters used 84.26% more than tuned. Holt–Winters responded earliest
  at the frozen growth threshold, but it also began and remained at higher
  capacity. That is aggressive scaling, not causal proof of anticipation.
- **Stepped:** among accepted arms, Holt–Winters traded 121.80% more capacity for
  a 16.57-percentage-point lower overall error rate than tuned. Both had zero
  errors in the frozen 120 seconds after the analyzed upward step. Neither raised
  desired replicas in the preceding 60 seconds, so genuine proactive anticipation
  was not observed at that step.
- **Chaotic:** the accepted soft arm saturated badly and host load reached
  106.35. Two Holt–Winters attempts ended in host freezes and tuned HPA was never
  started. No controller comparison is permissible.
- **Guarded chaotic:** all three arms served every request. Tuned used 16.46%
  fewer pod-seconds than soft and 26.26% fewer than Holt–Winters. This is one
  fixed-order run at 10–45 RPS, not a repetition or repair of the 20–120 RPS
  safety-stopped experiment.

## Historical live capacity-only results

These older runs contain replica/CPU telemetry but no per-request outcomes or
latency. Their three repeats support sample SD for capacity, not QoS. They must
not be pooled with the table above.

| Pattern | Controller | n | Pod-s mean ± SD | Hot fraction mean ± SD | QoS |
|---|---|---:|---:|---:|---|
| Seasonal | Soft HPA | 3 | 943.01 ± 94.07 | 0.850 ± 0.089 | NOT MEASURED |
| Seasonal | Tuned HPA | 3 | 583.25 ± 79.59 | 0.951 ± 0.050 | NOT MEASURED |
| Seasonal | Holt–Winters | 3 | 766.80 ± 39.61 | 0.865 ± 0.056 | NOT MEASURED |
| Burst | Soft HPA | 3 | 1088.25 ± 274.75 | 0.554 ± 0.096 | NOT MEASURED |
| Burst | Tuned HPA | 3 | 653.40 ± 24.74 | 0.806 ± 0.086 | NOT MEASURED |
| Burst | Holt–Winters | 3 | 728.38 ± 46.49 | 0.699 ± 0.133 | NOT MEASURED |

Within both patterns, tuned HPA used fewer pod-seconds than Holt–Winters. The
higher tuned hot fraction shows reduced spare capacity; absent request QoS, it
does not establish equivalent service. Full paired differences are in
`results/results.md`.

## Offline forecasting and released online evidence

The D1 evaluation covers 600 held-out scenarios (100 per pattern), five model
variants, and 15/60-minute rolling horizons. At one step, persistence had the
lowest mean MAE for burst (1.0375), chaotic (2.6700), growing (0.3659), and
stepped (0.6099); GBDT led on/off (5.5859) and seasonal (0.5326). At four steps,
the same pattern-level winners held except burst, where GBDT led at 2.2975.
These forecasting errors are not autoscaling request error rates and imply no
measured capacity or latency outcome. See `results/dataset_phase/offline_results.md`.

The D2 audit covers all 42 authors' traces and reproduces all 36 released
first-desired-increase timing entries arithmetically. Holt–Winters' released
advantage over HPA is 20.48 s (burst), 30.85 s (chaotic), 30.72 s (growing),
40.93 s (on/off), 30.77 s (seasonal), and 30.71 s (stepped). This confirms the
released data, not independent live reproduction or causal peak anticipation.
See `results/dataset_phase/online_results.md`.

## Rejected and inconclusive supplementary evidence

| Evidence | Disposition | Why it is excluded |
|---|---|---|
| Stepped soft HPA | REJECT | Dispatch p99 0.3148 s exceeded the frozen 0.100 s generator-integrity threshold. Its 0.89% errors and 9969.99 pod-s remain descriptive only. |
| NASA tuned repeat 3, two attempts | INCONCLUSIVE | CPU coverage was 75/84 = 89.3%, below the unchanged 90% rule. Including telemetry-complete repeats only can bias the tuned aggregate. |
| Chaotic Holt–Winters, two attempts | INCOMPLETE / EXCLUDED | Host froze twice; neither attempt has complete accounting or final analyzer artifacts. |
| Chaotic tuned HPA | NOT MEASURED | It was not started after the safety stop. |

## Central research interpretation

Tuned reactive HPA was competitive with Holt–Winters when the offered workload
was serviceable without predictive overprovisioning: the historical seasonal
and burst capacity-only runs, and the newer growing and Alibaba-derived runs.
In growing and Alibaba-derived evidence, tuned/soft reactive controllers
preserved the observed success rate at lower capacity; in historical seasonal
and burst, QoS equivalence is unknown because it was not instrumented.

Prediction helped most under sustained overload or sharp availability stress.
In NASA-derived and on/off replays, Holt–Winters substantially reduced errors
and successful-request p95 while consuming much more capacity. In stepped,
Holt–Winters lowered overall errors at more than twice tuned capacity, although
both accepted arms handled the analyzed upward transition without errors and
neither pre-scaled. The evidence therefore supports a capacity/QoS tradeoff,
not a universal predictive advantage.

No local transition establishes genuine proactive anticipation. Earlier
response can arise from higher starting replicas, controller cadence, or more
aggressive scaling. The 90× compression makes ten-second source bins shorter
than the 15-second CPU/HPA cadence, distorts cold starts and stabilization, and
prevents native-time claims. Mappings also differ: synthetic pod-count proxies
are affinely mapped to 20–120 HTTP requests/s, NASA request counts use their own
normalization, and Alibaba CPU observations are normalized after irregular
source time is discarded. Cross-workload raw costs are consequently not
exchangeable.

All newer runs used a single-node kind host with fixed order and uncontrolled
contention. Most patterns have only one accepted repetition; NASA is the only
newer repeated workload and its tuned arm has n=2 after telemetry exclusions.
The chaotic freeze demonstrates that host stability can dominate the measured
system. Findings are bounded to these replay protocols and do not generalize to
production Kubernetes deployments.

## Instrumentation limits

- Successful-request latency excludes failures; error/timeout denominators do
  not. No production SLA was predeclared.
- Per-request backend identity is unavailable, and probe-driven restarts can
  affect both availability and telemetry.
- Historical results have no request-level QoS. D2's 183 `ready > current` rows
  are retained as an asynchronous-status quality flag.
- Accepted single runs have no variance estimate. Mean ± sample SD is shown
  only for actual repeated measurements, never across incompatible workloads.
- The predictor configuration was not retuned per replay; the historical
  60-second Holt–Winters season also mismatches the roughly 80-second seasonal
  load period.
