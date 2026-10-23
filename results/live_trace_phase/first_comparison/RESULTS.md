# First verified live NASA three-controller comparison

These are preliminary single-repeat observations from real Kubernetes execution, not statistically reliable conclusions. Every arm used the same predetermined NASA-derived schedule, application, resources, 120-second warmup, and 420-second measurement window.

## Measurements

| Arm | Success / 26,103 | Error rate | Timeout / disconnect | Success latency p50 / p95 / p99 (s) | Success rps | Pod-s | Mean / max ready | CPU mean / max (m) | Hot CPU fraction | Restarts | Dispatch p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | 13,117 | 49.75% | 12,956 / 30 | 0.008 / 2.036 / 4.355 | 31.23 | 1067.50 | 2.54 / 6 | 232.2 / 499.9 | 42.31% | 4 | 2.409 |
| Tuned HPA (70%) | 16,682 | 36.09% | 9,404 / 17 | 0.007 / 2.457 / 4.530 | 39.72 | 927.50 | 2.21 / 4 | 222.9 / 500.0 | 46.43% | 4 | 2.220 |
| Holt–Winters PHPA | 20,939 | 19.78% | 5,160 / 4 | 0.008 / 0.486 / 4.086 | 49.85 | 3497.50 | 8.33 / 10 | 113.4 / 497.0 | 21.43% | 1 | 2.250 |

All arms scheduled and recorded 26,583 total requests: 480 warmup plus 26,103 measurement. Offered measurement load was 62.15 requests/s. Generator drops were zero. The protocol defines no SLA threshold, so SLA violations are **NOT DEFINED**. Latency percentiles include successful requests only; all failures remain in the error-rate denominator.

## Scaling and readiness

- Soft HPA (50%): 1→5 at measurement +185s, 5→4 at measurement +260s, 4→6 at measurement +410s; 28 readiness-deficit samples; 19 readiness and 6 liveness probe failures.
- Tuned HPA (70%): 1→2 at measurement +15s, 2→3 at measurement +185s, 3→4 at measurement +410s; 25 readiness-deficit samples; 37 readiness and 12 liveness probe failures.
- Holt–Winters PHPA: 1→5 at measurement +35s, 5→10 at measurement +95s; 10 readiness-deficit samples; 30 readiness and 9 liveness probe failures.

## Preliminary differences versus soft HPA

- Tuned HPA reduced error rate by 13.66 percentage points and pod-seconds by 13.1%, while successful-request p95 latency was 20.7% higher.
- Holt–Winters reduced error rate by 29.97 percentage points and successful-request p95 latency by 76.2%, but used 227.6% more pod-seconds.
- These capacity/QoS tradeoffs are descriptive only. With one repeat per controller, order and host effects cannot be separated from controller effects.

## Validity

All three arms were `ACCEPT` under the predeclared analyzer checks. Each had exact request accounting, no unexplained missing or duplicate rows, zero generator drops, dispatch p99 below 3 ms (threshold 100 ms), exclusive intended-controller ownership, a bracketed measurement window, five-second-scale telemetry gaps, and scaling above one replica. CPU was present in 78/84 soft-HPA samples and 84/84 samples for each other arm. Independent recomputation agreed with the analyzer for request counts, error rate, successful-latency population, pod-seconds, controller identity, and 420-second measurement duration for every arm.

The high error rates remain experimental outcomes. Probe paths and ports were functional at idle; timeouts, readiness deficits, and liveness restarts under load support service saturation/unavailability rather than generator loss. Per-request backend identity was not captured, so attribution of each individual failure remains limited.

## Evidence

Machine-readable results are in `comparison.csv` and `comparison.json`. `evidence_manifest.json` maps reported calculations to raw files and SHA-256 hashes. Exact commands are in `REPRODUCE.md`; the frozen order and preflight decision are in `run_plan.json` and `PREFLIGHT.md`.
