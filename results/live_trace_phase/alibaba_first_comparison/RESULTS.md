# First Alibaba-derived live comparison

Alibaba-trace-derived demand replay on a benchmark Kubernetes service.

One repetition per controller; values are descriptive and no between-repeat variance is available.

| Controller | Decision | Error | Success p95 / p99 (s) | Pod-s | Pod-s / success | Mean / max ready | CPU coverage | Scaling events |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | ACCEPT | 0.00% | 0.009 / 0.012 | 1277.50 | 0.08859 | 3.04 / 6 | 100.00% | 7 |
| Tuned HPA (70%) | ACCEPT | 0.00% | 0.008 / 0.012 | 1317.50 | 0.09137 | 3.14 / 4 | 100.00% | 3 |
| Holt-Winters PHPA | ACCEPT | 0.00% | 0.015 / 0.283 | 1422.50 | 0.09865 | 3.39 / 5 | 100.00% | 5 |

Latency percentiles contain successful requests only; all failures remain in the scheduled-request denominator. No production SLA is defined.

All arms scheduled and recorded 14,900 requests: 480 warmup plus 14,420 measurement. Generator drops, timeouts, disconnects, HTTP failures, workload restarts, and probe failures were all zero. Dispatch p99 was 2.166 ms (soft), 2.145 ms (tuned), and 2.955 ms (Holt–Winters). CPU metrics were available in 84/84 measurement samples for every arm. Soft HPA used the fewest pod-seconds; tuned used 40.00 more (+3.13%) and Holt–Winters used 145.00 more (+11.35%).

## Validity

All independent source-hash, schedule, request, latency, pod-second, controller-exclusivity, duration, and dispatch checks passed. Per-arm acceptance decisions remain those of the frozen framework; poor service performance is not an instrumentation rejection.

## Limitations

The prefix and `c_1` were not randomly sampled. The transformation discards irregular source timing and normalizes CPU telemetry into HTTP request rate, changing both time structure and absolute amplitude. Order effects, host contention, a single repetition, single-node kind, probe-driven restarts, and missing per-request backend identity limit inference. These results do not represent the full Alibaba dataset or Alibaba production services.
