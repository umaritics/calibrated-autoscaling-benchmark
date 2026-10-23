# First verified live growing comparison

accelerated D1 synthetic growing pod-demand-proxy replay on a benchmark Kubernetes service.

One repeat per controller; all comparisons are descriptive.

| Controller | Decision | Errors / timeout | Success p95 / p99 (s) | Pod-s | Mean / max ready | CPU coverage | CPU mean / max (m) | Scale changes | Dispatch p99 (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Soft HPA (50%) | ACCEPT | 0.00% / 0.00% | 0.009 / 0.012 | 1927.50 | 4.59 / 8 | 100.00% | 111.3 / 184.5 | 7 | 0.0020 |
| Tuned HPA (70%) | ACCEPT | 0.00% / 0.00% | 0.010 / 0.013 | 1572.50 | 3.74 / 6 | 100.00% | 136.7 / 213.8 | 5 | 0.0020 |
| Holt-Winters PHPA | ACCEPT | 0.00% / 0.00% | 0.012 / 0.021 | 2897.50 | 6.90 / 12 | 100.00% | 82.0 / 179.9 | 11 | 0.0021 |

All 92,199 scheduled measurement requests across the three arms succeeded. Tuned HPA used 18.42% fewer ready-pod-seconds than soft HPA while preserving the same observed success rate. Holt-Winters used 50.32% more than soft HPA and 84.26% more than tuned HPA. Its successful-request p95 was also higher (0.012 s versus 0.009–0.010 s), although all absolute latencies were low and no SLA was predeclared.

## Growth-specific observations

Sustained-growth onset is predeclared at measurement second 200: the first three consecutive 10-second bins at or above 70 requests/s. Response delay is the first desired/ready increase above the last pre-onset sample. Early and late windows are [0,140) and [280,420) seconds.

| Controller | Desired / ready response delay (s) | Early → late mean ready | Early → late errors | First ready rise before onset |
|---|---:|---:|---:|---:|
| Soft HPA (50%) | 60.00 / 65.00 | 2.23 → 6.75 | 0.00% → 0.00% | True |
| Tuned HPA (70%) | 30.00 / 40.00 | 1.96 → 5.77 | 0.00% → 0.00% | True |
| Holt-Winters PHPA | 5.00 / 0.00 | 3.29 → 9.91 | 0.00% → 0.00% | True |

A pre-onset replica increase is temporal evidence only; it is not, by itself, proof of proactive prediction. Capacity and QoS are reported separately, and lower pod-seconds is not treated as better service.

All controllers raised ready capacity from the early to the late window and sustained the complete offered throughput without failures. Relative to the last sample before the 70 requests/s threshold, Holt-Winters increased desired/ready replicas about 5/0 seconds after onset, tuned HPA about 30/40 seconds after, and soft HPA about 60/65 seconds after. Holt-Winters therefore responded earliest by this frozen criterion, but it also held 9.91 mean late-window replicas versus 6.75 soft and 5.77 tuned, and changed desired replicas 11 times versus 7 and 5. This is consistent with a faster, more aggressive response; it does not establish that the response was causally proactive.

## Verification

Run disposition: 3 accepted, 0 inconclusive, and 0 rejected. The independent verifier reconstructed every deterministic request key, schedule hash, request outcome, successful-latency population, dispatch delay, ready-pod integral, controller identity, source replay hash, and measurement window. All independent cross-checks passed. Per-run acceptance uses the unchanged analyzer thresholds, including at least 90% CPU coverage.

## Limitations

This is one repeat on a single-node kind cluster. The source is synthetic pod-count demand, affinely mapped to HTTP requests and compressed 90×; it is not native-time replay or production traffic. Ten-second bins are shorter than the 15-second CPU metric/HPA cadence, so only the sustained 420-second rise is interpreted. Fixed arm order and uncontrolled host contention remain limitations. The PHPA configuration was not retuned for this workload.
