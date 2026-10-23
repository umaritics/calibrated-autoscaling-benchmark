# NASA trace-replay findings — partial repetition milestone

## Scope and status

This is a NASA-derived demand replay against this project's CPU-bound benchmark
service on a single-node kind cluster. It is not a reproduction of NASA's
original infrastructure or application. Eight of the required nine runs are
accepted. Repeat 3 tuned HPA remained `INCONCLUSIVE` after one unchanged retry,
so tuned-HPA aggregates are n=2 and the milestone is **PARTIAL**.

## Executed matrix

| Repeat | Position | Controller | Decision |
|---:|---:|---|---|
| 1 | 1 | Soft HPA | ACCEPT |
| 1 | 2 | Tuned HPA | ACCEPT |
| 1 | 3 | Holt-Winters | ACCEPT |
| 2 | 1 | Tuned HPA | ACCEPT |
| 2 | 2 | Holt-Winters | ACCEPT |
| 2 | 3 | Soft HPA | ACCEPT |
| 3 | 1 | Holt-Winters | ACCEPT |
| 3 | 2 | Soft HPA | ACCEPT |
| 3 | 3 | Tuned HPA | INCONCLUSIVE (two retained attempts) |

Both tuned-HPA attempts had exact request accounting, zero generator drops,
exclusive controller ownership, bracketed windows, five-second telemetry
spacing, and observed scaling. Each had CPU values for 75/84 samples (89.3%),
below the fixed 90% threshold. The empty metrics bursts coincided with pod
unavailability/restarts and HPA `no metrics returned` events; counting either
attempt could bias the comparison.

## Accepted-run aggregate

Values are mean ± sample SD. Latency percentiles contain successful requests
only; failures remain in error and timeout denominators.

| Controller | n | Error rate | Timeout rate | Success p95 (s) | Success p99 (s) | Success rps | Pod-s | Mean ready | Max ready | Pod-s / success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Soft HPA | 3 | 44.76% ± 9.37% | 44.64% ± 9.32% | 2.508 ± 0.918 | 4.520 ± 0.187 | 34.33 ± 5.82 | 1192.50 ± 156.12 | 2.839 ± 0.372 | 6.00 ± 2.00 | 0.08455 ± 0.02005 |
| Tuned HPA | 2 | 37.75% ± 2.34% | 37.64% ± 2.28% | 2.241 ± 0.306 | 4.503 ± 0.039 | 38.69 ± 1.46 | 915.00 ± 17.68 | 2.179 ± 0.042 | 4.00 ± 0.00 | 0.05633 ± 0.00103 |
| Holt-Winters | 3 | 18.04% ± 2.05% | 18.02% ± 2.06% | 0.868 ± 0.653 | 3.964 ± 0.499 | 50.94 ± 1.28 | 3479.17 ± 20.21 | 8.284 ± 0.048 | 10.00 ± 0.00 | 0.16271 ± 0.00498 |

The explicit efficiency metric is ready-pod-seconds divided by successful
measurement requests. It captures capacity consumed per delivered success, but
does not price CPU intensity, startup transients, or quality differences among
successful responses.

Full aggregates for scaling changes, readiness deficits, observed CPU, and
generator dispatch p99 are in `mean_sd.csv`.

## Paired differences and ranking

Differences are left controller minus right controller, paired by repeat.

| Comparison | n | Error-rate difference | Success-p95 difference (s) | Pod-s difference |
|---|---:|---:|---:|---:|
| Soft minus Holt-Winters | 3 | +26.72 ± 7.47 percentage points | +1.640 ± 1.387 | -2286.67 ± 159.40 |
| Tuned minus Holt-Winters | 2 | +18.58 ± 3.21 percentage points | +1.187 ± 1.110 | -2575.00 ± 7.07 |
| Soft minus tuned | 2 | +12.41 ± 1.76 percentage points | -0.262 ± 0.225 | +302.50 ± 229.81 |

Holt-Winters had the lowest error rate and successful-request p95 in every
accepted paired repeat, but used the most pod-seconds in every repeat. Tuned HPA
had fewer errors and used fewer pod-seconds than soft HPA in both valid paired
repeats, while soft HPA's successful-request p95 was slightly lower in both.
These rankings are consistent within available valid pairs, but the tuned
repeat-3 gap prevents a complete n=3 comparison.

Over repeats 1-2, the predictor's error-rate advantage was 12.41 percentage
points smaller against tuned HPA than against soft HPA. Algebraically this is
exactly the soft-versus-tuned baseline difference; it measures how baseline
calibration changes the apparent advantage and does not isolate predictive
behavior.

## QoS versus capacity

Holt-Winters' lower errors, lower success latency, and higher success throughput
came with about 2.9x the soft-HPA pod-seconds and 3.8x the accepted tuned-HPA
pod-seconds. Its pod-seconds per success was also worst. Tuned HPA's accepted
repeats improved error rate and capacity over soft HPA without more pod-seconds,
but did not beat Holt-Winters' QoS. This is a capacity/QoS tradeoff, not evidence
of statistical significance.

## Limitations

The trace is one fixed, compressed NASA-derived demand shape, not independent
production workloads. n=3 is descriptive and cannot support a significance or
generalization claim; tuned HPA has only n=2 accepted repeats. Host contention,
single-node kind scheduling, probe-driven application restarts, absent per-
request backend identity, and the repeated metrics gap are material threats.
