# First verified live stepped comparison

accelerated D1 synthetic stepped pod-demand-proxy replay on a benchmark Kubernetes service.

One repeat per controller; all comparisons are descriptive.

| Controller | Decision | Errors / timeout | Success p50 / p95 / p99 (s) | Success RPS | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scale changes | Dispatch p99 (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tuned HPA (70%) | ACCEPT | 17.58% / 17.54% | 0.008 / 0.011 / 2.442 | 58.09 | 5872.50 | 0.08424 | 4.89 / 7 | 97.50% | 6 | 0.0022 |
| Holt-Winters PHPA | ACCEPT | 1.01% / 1.00% | 0.008 / 0.016 / 1.999 | 69.77 | 13025.00 | 0.15557 | 10.85 / 15 | 100.00% | 14 | 0.0021 |
| Soft HPA (50%) | REJECT | 0.89% / 0.89% | 0.009 / 0.790 / 3.407 | 69.85 | 9969.99 | 0.11894 | 8.31 / 20 | 100.00% | 13 | 0.3148 |

## Transition observations

Boundaries and 120-second post-step windows were frozen before execution. Response lag is measured from the observed source boundary to the first matching desired/ready change relative to the last pre-boundary telemetry sample. Up-step capacity is called sufficient only when the first 30 seconds has zero failures. Down-step excess is ready-pod-seconds above the minimum ready count in the plateau's final 60 seconds. Collector resolution is about five seconds, so finer lag distinctions are not claimed.

| Controller | Down desired / ready lag (s) | Low-plateau excess pod-s | Down-window errors | Up desired / ready lag (s) | Up-window errors | First-30s capacity sufficient | Desired rise in pre-step 60s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tuned HPA (70%) | 315.00 / 315.00 | 1652.50 | 0.00% | 40.00 / 45.00 | 0.00% | True | False |
| Holt-Winters PHPA | 15.00 / 15.00 | 2817.50 | 0.00% | 45.00 / 50.00 | 0.00% | True | False |
| Soft HPA (50%) | 75.00 / 75.00 | 1335.00 | 0.00% | 25.00 / 30.00 | 0.00% | True | False |

## Cost and request quality

Among accepted arms, Holt-Winters PHPA had the lowest error rate (1.01%); Tuned HPA (70%) used the fewest ready-pod-seconds (5872.50). Holt-Winters used 121.80% more ready-pod-seconds than tuned HPA while reducing errors by 16.57% percentage points. The rejected soft-HPA arm recorded 0.89% errors and 9969.99 pod-seconds, but its 0.315-second dispatch p99 exceeded the frozen 0.100-second threshold, so those observations are not used for a valid causal controller comparison. Successful-request latency is interpreted only alongside scheduled-request error rate, never alone.

Holt-Winters is described as temporally pre-scaling only if the frozen up-step metric reports a desired increase in the preceding 60 seconds. Holding more replicas by itself is not treated as proactivity.

At the upward boundary, tuned HPA changed desired/ready replicas in 40/45 seconds and Holt-Winters in 45/50 seconds. Both had zero failures in the frozen 120-second window, and neither increased desired replicas during the preceding 60 seconds. Thus prediction was not proactive at this observed step, and tuned HPA was competitive for abrupt-change QoS. The five-second difference is one collector interval and is not treated as a reliable fine-grained ordering.

At the downward boundary, tuned HPA delayed its first desired/ready decrease for 315 seconds, consistent with its unchanged 300-second stabilization. Holt-Winters decreased after 15 seconds but still held more excess capacity over the low plateau (2817.50 versus 1652.50 pod-seconds) because it entered the plateau at a much higher replica count.

Errors were concentrated in the initial [0,400) plateau before the analyzed up-step: 49.17% tuned versus 2.82% Holt-Winters. Later accepted-arm plateaus had zero errors. Workload restarts were 3 tuned and 0 Holt-Winters; the rejected soft arm recorded 0.

## Verification

Run disposition: 2 accepted, 0 inconclusive, and 1 rejected. The independent verifier reconstructed every deterministic request key, schedule hash, outcome denominator, successful-latency population, dispatch delay, ready-pod integral, controller identity, source/replay hash, transition timing, and measurement duration. All cross-checks passed. Per-run acceptance retains the unchanged analyzer thresholds, including at least 90% CPU coverage.

## Limitations

This is one repeat on a single-node kind cluster, so there is no variance estimate or causal generalization. The source is synthetic pod-count demand affinely mapped to HTTP rate, not observed traffic. The 90× time compression changes physical meaning; individual 10-second noisy bins are below HPA metric resolution even though the 400-second plateaus are observable. Fixed arm order, host contention, a PHPA configuration not retuned for this workload, and only one transition per direction remain limitations. The longer duration differs from growing/on-off; cross-pattern raw cost comparisons must normalize by demand and time.
