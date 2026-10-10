# Measured results

Every figure below was computed from a CSV under `output/our_study/runs`. Missing runs are `NOT MEASURED`. No latency or SLA column exists because the collector does not record requests.

## Per run

| Repeat | Pattern | Arm | Rows | Mean ready replicas | Max ready | Pod-seconds | Mean CPU millicores | Desired-replica changes | First time ready>=2 (s) | Hot fraction |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| repeat1 | seasonal | strawman_hpa | 19 | 7.26 | 20 | 895.62 | 258.91 | 5 | 31.0 | 0.789 |
| repeat1 | seasonal | holtwinters | 19 | 6.53 | 10 | 812.20 | 268.88 | 3 | 6.6 | 0.895 |
| repeat1 | seasonal | calibrated_hpa | 19 | 5.05 | 8 | 620.16 | 302.68 | 6 | 11.9 | 1.000 |
| repeat1 | burst | strawman_hpa | 18 | 12.06 | 20 | 1447.39 | 174.73 | 3 | 12.7 | 0.444 |
| repeat1 | burst | holtwinters | 17 | 6.06 | 10 | 753.96 | 233.06 | 2 | 18.3 | 0.647 |
| repeat1 | burst | calibrated_hpa | 20 | 5.70 | 9 | 690.84 | 238.96 | 4 | 0.0 | 0.750 |
| repeat2 | seasonal | strawman_hpa | 21 | 8.67 | 20 | 1081.08 | 259.14 | 5 | 11.1 | 0.952 |
| repeat2 | seasonal | holtwinters | 20 | 6.55 | 10 | 829.23 | 264.13 | 3 | 6.3 | 0.900 |
| repeat2 | seasonal | calibrated_hpa | 20 | 5.45 | 9 | 681.25 | 316.93 | 4 | 12.0 | 0.900 |
| repeat2 | burst | strawman_hpa | 21 | 7.38 | 18 | 906.75 | 242.07 | 4 | 28.3 | 0.619 |
| repeat2 | burst | holtwinters | 20 | 6.35 | 10 | 773.43 | 231.96 | 3 | 5.7 | 0.600 |
| repeat2 | burst | calibrated_hpa | 21 | 5.14 | 9 | 622.08 | 262.93 | 6 | 11.6 | 0.905 |
| repeat3 | seasonal | strawman_hpa | 21 | 7.76 | 20 | 960.07 | 286.14 | 4 | 27.7 | 0.810 |
| repeat3 | seasonal | holtwinters | 20 | 6.15 | 10 | 758.91 | 257.32 | 2 | 17.8 | 0.800 |
| repeat3 | seasonal | calibrated_hpa | 21 | 4.24 | 8 | 524.21 | 313.54 | 5 | 27.9 | 0.952 |
| repeat3 | burst | strawman_hpa | 20 | 8.60 | 16 | 1014.80 | 218.57 | 5 | 12.4 | 0.600 |
| repeat3 | burst | holtwinters | 20 | 5.65 | 10 | 679.13 | 249.33 | 4 | 16.9 | 0.850 |
| repeat3 | burst | calibrated_hpa | 21 | 5.52 | 9 | 691.36 | 270.91 | 4 | 11.6 | 0.762 |

## Mean across repeats

| Pattern | Arm | Repeats found | Mean pod-seconds | Mean hot fraction | Mean desired-replica changes |
|---|---|---:|---:|---:|---:|
| seasonal | strawman_hpa | 3 | 978.92 | 0.850 | 4.67 |
| seasonal | holtwinters | 3 | 800.11 | 0.865 | 2.67 |
| seasonal | calibrated_hpa | 3 | 608.54 | 0.951 | 5.00 |
| burst | strawman_hpa | 3 | 1122.98 | 0.554 | 4.00 |
| burst | holtwinters | 3 | 735.51 | 0.699 | 3.00 |
| burst | calibrated_hpa | 3 | 668.09 | 0.806 | 4.67 |

## Derived arms (no extra cluster run)

Component B uses Holt–Winters on seasonal and strawman HPA on burst. Components A+B use Holt–Winters on seasonal and calibrated HPA on burst. The numbers are the same CSV means as the selected arm.

| Pattern | Derived arm | Selected measured arm | Mean pod-seconds | Mean hot fraction |
|---|---|---|---:|---:|
| seasonal | B_switch_strawman | holtwinters | 800.11 | 0.865 |
| burst | B_switch_strawman | strawman_hpa | 1122.98 | 0.554 |
| seasonal | AB_switch_calibrated | holtwinters | 800.11 | 0.865 |
| burst | AB_switch_calibrated | calibrated_hpa | 668.09 | 0.806 |

## Calibration gap

`advantage_vs_reactive = pod_seconds(reactive) - pod_seconds(holtwinters)`. Positive means Holt–Winters used fewer pod-seconds.
`calibration_gap = advantage_vs_strawman - advantage_vs_calibrated`. Positive means some of the Holt–Winters win existed only against the 50% HPA.

| Pattern | Mean pod-seconds strawman | Mean pod-seconds Holt–Winters | Mean pod-seconds calibrated | Advantage vs strawman | Advantage vs calibrated | Calibration gap |
|---|---:|---:|---:|---:|---:|---:|
| seasonal | 978.92 | 800.11 | 608.54 | 178.81 | -191.57 | 370.38 |
| burst | 1122.98 | 735.51 | 668.09 | 387.47 | -67.41 | 454.89 |

## Files read

- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/seasonal/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/seasonal/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/seasonal/calibrated_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/burst/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/burst/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat1/burst/calibrated_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/seasonal/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/seasonal/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/seasonal/calibrated_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/burst/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/burst/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat2/burst/calibrated_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/seasonal/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/seasonal/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/seasonal/calibrated_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/burst/strawman_hpa.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/burst/holtwinters.csv`
- ok: `/root/calibrated-autoscaling-work/workloads-predictional-scaling-operators/output/our_study/runs/repeat3/burst/calibrated_hpa.csv`
