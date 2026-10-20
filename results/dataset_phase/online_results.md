# Authors’ online traces: independent audit

These are the authors’ released runs, not new cluster experiments. All 42 traces and 36 early-detection entries are included. No tuned-HPA trace or repeated trials exists in this release. The separate `online_summary.csv` describes static-load scenarios and is inventoried but not pooled with pattern runs.

## Holt–Winters timing comparison

| pattern | released_early_s | first_desired_advantage_s | difference_s | first_ready_advantage_s |
|---|---|---|---|---|
| burst | 20.48 | 20.48 | -0.0 | 20.5 |
| chaotic | 30.85 | 30.85 | 0.0 | 25.84 |
| growing | 30.72 | 30.72 | 0.0 | 30.74 |
| onoff | 40.93 | 40.93 | 0.0 | 40.92 |
| seasonal | 30.77 | 30.77 | 0.0 | 30.76 |
| stepped | 30.71 | 30.71 | -0.0 | 30.71 |

Across all 36 entries, 36 match our first-desired-increase calculation within 1e-9 seconds. This verifies arithmetic on released traces, not an independent live replication.

Released early detection is copied from the supplied summary. Our alternative definition is the HPA time of the first observed increase in desired replicas minus the PHPA time of its first increase. Ready-replica timing is shown separately. Initial nonzero replicas are not a scale-up event; events during warmup cannot be recovered. A mismatch is a definition/provenance issue, not evidence that either timing measures anticipation of a workload peak.

## Capacity over each recorded window

| pattern | model | rows | duration_s | pod_seconds | time_mean_ready | hot_fraction | ready_gt_current_rows |
|---|---|---|---|---|---|---|---|
| burst | baseline_hpa | 59 | 297.22 | 4404.655 | 14.82 | 0.61 | 31 |
| burst | phpa_holtwinters | 59 | 297.38 | 4806.75 | 16.164 | 0.576 | 0 |
| chaotic | baseline_hpa | 59 | 298.97 | 4495.9 | 15.038 | 0.898 | 30 |
| chaotic | phpa_holtwinters | 59 | 297.87 | 4804.635 | 16.13 | 0.915 | 0 |
| growing | baseline_hpa | 59 | 297.13 | 4444.25 | 14.957 | 0.831 | 30 |
| growing | phpa_holtwinters | 59 | 298.21 | 4804.08 | 16.11 | 0.847 | 0 |
| onoff | baseline_hpa | 59 | 297.19 | 4471.05 | 15.044 | 0.712 | 31 |
| onoff | phpa_holtwinters | 59 | 297.41 | 4724.3 | 15.885 | 0.576 | 0 |
| seasonal | baseline_hpa | 59 | 297.36 | 4492.61 | 15.108 | 0.712 | 31 |
| seasonal | phpa_holtwinters | 59 | 297.38 | 4832.17 | 16.249 | 0.797 | 0 |
| stepped | baseline_hpa | 59 | 297.21 | 4445.325 | 14.957 | 0.644 | 30 |
| stepped | phpa_holtwinters | 59 | 297.45 | 4925.78 | 16.56 | 0.712 | 0 |

Data-quality flag: 183 rows report ready replicas greater than current replicas. These fields may reflect asynchronous status sources; the integral uses the released ready column without correction. Hot fraction uses the same 160 m threshold as our existing study, not a latency measure. Durations differ: compare time-mean ready replicas alongside raw pod-seconds. Single runs do not support uncertainty estimates or causal controller rankings. All models are in `online_trace_metrics.csv`.
