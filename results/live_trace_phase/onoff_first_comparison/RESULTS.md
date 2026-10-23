# First verified live on/off comparison

D1 synthetic on/off pod-demand-proxy replay on a benchmark Kubernetes service.

One repeat per controller; all comparisons are descriptive.

| Controller | Decision | Errors | Timeout | Success p95 / p99 (s) | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scale changes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | ACCEPT | 50.05% | 49.99% | 1.456 / 4.307 | 1612.50 | 0.10785 | 3.84 / 10 | 92.86% | 7 |
| Tuned HPA (70%) | ACCEPT | 48.55% | 48.46% | 1.069 / 4.346 | 1332.50 | 0.08654 | 3.17 / 6 | 92.86% | 3 |
| Holt-Winters PHPA | ACCEPT | 13.29% | 13.20% | 0.050 / 3.431 | 3542.50 | 0.13651 | 8.43 / 13 | 100.00% | 8 |

Run disposition: 3 accepted, 0 inconclusive, and 0 rejected.
Successful-request latency excludes failures; every failure remains in the scheduled-request denominator. All arms retained 29,930 measurement records with zero generator drops; each workload experienced three restarts. Readiness-deficit samples were 33 (soft), 31 (tuned), and 17 (Holt-Winters).

Holt-Winters had 13.29% errors versus 50.05% soft and 48.55% tuned, while consuming 119.7% more ready-pod-seconds than soft and 165.9% more than tuned. Tuned used 17.4% fewer ready-pod-seconds than soft but did not materially avoid overload.

## Transition observations

The frozen measurement has a high→low boundary at 160 s and a low→high boundary at 320 s. Scale response is the first observed desired/ready change in the matching direction relative to the last pre-boundary telemetry sample. Low-period excess capacity is ready-pod-seconds above the fixed one-pod minimum over [160,320). Activation QoS uses scheduled requests in [320,380). A missing delay means the matching response was not observed before measurement end; none of these definitions claims proactive forecasting.

| Controller | Desired / ready down delay (s) | Low excess pod-s | Desired / ready up delay (s) | Activation errors | Activation success p95 (s) | Activation hot-CPU samples |
|---|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | not observed / 0.00 | 800.00 | 30.00 / 35.00 | 0.00% | 0.010 | 66.67% |
| Tuned HPA (70%) | not observed / 5.00 | 527.50 | not observed / not observed | 0.00% | 0.010 | 0.00% |
| Holt-Winters PHPA | not observed / not observed | 1440.00 | 65.00 / 70.00 | 0.00% | 0.013 | 0.00% |

## Verification

The independent verifier reconstructed every deterministic request key, request outcome, latency population, dispatch delay, ready-pod integral, controller identity, source hash, and measurement duration from raw evidence. All independent checks passed. Per-run acceptance still comes from the pre-existing analyzer thresholds.

## Limitations

This is one repeat per controller on one single-node kind cluster. The source is synthetic pod-count demand, not request telemetry; mapping it to HTTP rate and compressing time 90× changes its physical meaning. Arm order is fixed, host contention is uncontrolled, the PHPA seasonal period is not retuned to this source, and per-request backend identity is unavailable. Transition metrics have one event of each direction and therefore no variance or causal interpretation.
