# Live Kubernetes production-trace-derived replay results

Five bounded milestones are retained separately:

- NASA-derived replay: 8/9 accepted matrix, with 3 soft-HPA, 2 tuned-HPA,
  and 3 Holt–Winters accepted runs. Two tuned-HPA attempts remain
  `INCONCLUSIVE`; see `nasa_three_repeat/FINDINGS.md`.
- Alibaba-derived replay: one accepted run per controller; see
  `alibaba_first_comparison/RESULTS.md`.
- On/off D1-derived replay: one accepted run per controller; see
  `onoff_first_comparison/RESULTS.md`.
- Growing D1-derived replay: one accepted run per controller; see
  `growing_first_comparison/RESULTS.md`.
- Stepped D1-derived replay: tuned HPA and Holt–Winters accepted; soft HPA
  rejected on frozen generator-dispatch integrity; see
  `stepped_first_comparison/RESULTS.md`.

These are demand replays against the benchmark Kubernetes service, not
reproductions of either production service or the paper's forecast-MAPE
protocol.

## Growing first comparison

The frozen 420-second replay maps a deterministically selected 42-observation
growing window from synthetic pod-count proxy values to 20–120 HTTP requests/s.
All three arms passed the unchanged acceptance criteria and independently
verified exact accounting. Each completed all 30,733 measurement requests with
zero failures and zero generator drops.

| Controller | Error | Success p95 / p99 (s) | Pod-s | Mean / max ready | CPU coverage | Scale changes |
|---|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | 0.00% | 0.009 / 0.012 | 1927.50 | 4.59 / 8 | 100.00% | 7 |
| Tuned HPA (70%) | 0.00% | 0.010 / 0.013 | 1572.50 | 3.74 / 6 | 100.00% | 5 |
| Holt–Winters PHPA | 0.00% | 0.012 / 0.021 | 2897.50 | 6.90 / 12 | 100.00% | 11 |

Holt–Winters reacted earliest at the frozen growth threshold but used 50.32%
more pod-seconds than soft HPA and 84.26% more than tuned HPA. Tuned HPA used
18.42% fewer pod-seconds than soft HPA with the same observed success rate.
These are single-run descriptive comparisons; see
`growing_first_comparison/RESULTS.md` for growth-response definitions and
limitations.

## Stepped first comparison

The frozen 1,200-second replay maps D1 stepped scenario 62 observations 72–191
to 20–120 requests/s with no interpolation. It preserves three 400-second
plateaus and observed up/down boundaries at measurement seconds 400 and 800.

| Controller | Decision | Error | Success p95 / p99 (s) | Pod-s | Mean / max ready | CPU coverage | Dispatch p99 (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| Tuned HPA (70%) | ACCEPT | 17.58% | 0.011 / 2.442 | 5872.50 | 4.89 / 7 | 97.50% | 0.0022 |
| Holt–Winters PHPA | ACCEPT | 1.01% | 0.016 / 1.999 | 13025.00 | 10.85 / 15 | 100.00% | 0.0021 |
| Soft HPA (50%) | REJECT | 0.89% | 0.790 / 3.407 | 9969.99 | 8.31 / 20 | 100.00% | 0.3148 |

The accepted arms both had zero failures in the 120 seconds after the upward
step. Tuned HPA increased desired/ready capacity after 40/45 seconds and
Holt–Winters after 45/50 seconds; neither pre-scaled in the preceding 60
seconds. On the down-step, tuned HPA's first reduction was delayed 315 seconds,
consistent with its 300-second stabilization. Holt–Winters reduced after 15
seconds but entered with much more capacity and accumulated more excess
ready-pod-seconds. The rejected soft result is retained descriptively but is
not used for causal controller comparison.

## Alibaba first comparison

All arms used the same frozen 120-second warmup and 420-second measurement
schedule. Each scheduled and recorded 14,420 measurement requests with zero
errors, zero generator drops, exact schedule retention, 84/84 CPU samples,
exclusive controller ownership, and independently reproduced pod-seconds.

| Controller | Error | Success p95 / p99 (s) | Pod-s | Pod-s / success | Mean / max ready | Scaling changes |
|---|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | 0.00% | 0.009 / 0.012 | 1277.50 | 0.08859 | 3.04 / 6 | 7 |
| Tuned HPA (70%) | 0.00% | 0.008 / 0.012 | 1317.50 | 0.09137 | 3.14 / 4 | 3 |
| Holt–Winters PHPA | 0.00% | 0.015 / 0.283 | 1422.50 | 0.09865 | 3.39 / 5 | 5 |

In this single execution, soft HPA used the fewest pod-seconds. Tuned HPA used
40.00 more (+3.13%) and Holt–Winters used 145.00 more (+11.35%) than soft HPA.
Holt–Winters also had the highest successful-request p95/p99. These are
descriptive observations from one fixed, time-warped sequence; no variance or
significance claim is possible.

## Scope and limitations

The Alibaba input is a 16 MiB byte-range prefix, not a representative sample of
the full archive. The selected first 42 `c_1` observations span 33,120 irregular
source seconds and are mapped by observation index to equal ten-second replay
bins. This changes temporal structure; normalization from CPU percent to HTTP
request rate changes units and absolute amplitude. See
`alibaba_first_comparison/DATASET_VALIDATION.md` and
`alibaba_first_comparison/WORKLOAD_TRANSFORMATION.md`.

Latency percentiles include successful requests only; failures remain in the
scheduled-request denominator. No production SLA is defined. Single-node kind,
fixed run order, host contention, and one repetition are additional threats.
