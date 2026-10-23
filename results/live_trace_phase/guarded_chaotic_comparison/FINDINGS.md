# Guarded chaotic milestone findings

Status: **COMPLETE — guarded three-controller matrix executed once**.

Task 12's smoke attempt 3 remains failed. Protocol v2 prospectively replaced its unavailable user-scope cpuset-file observation with direct kernel scheduler-affinity read-back while retaining all cgroup budgets, watchdog thresholds, workload parameters, and scientific thresholds. See `affinity_revision_v2/SAFETY_PROTOCOL_V2.md`.

| Controller | Decision | Success | p50 ms | p95 ms | p99 ms | Pod-seconds | Pod-s/success | Mean ready | Max ready |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| calibrated_hpa | ACCEPT | 12532/12532 | 7.516 | 11.188 | 13.587 | 990.000 | 0.078998 | 2.357 | 3 |
| holtwinters | ACCEPT | 12532/12532 | 7.842 | 11.692 | 14.681 | 1342.499 | 0.107126 | 3.196 | 6 |
| strawman_hpa | ACCEPT | 12532/12532 | 7.802 | 11.678 | 14.499 | 1185.000 | 0.094558 | 2.821 | 3 |

All arms served every one of 12,532 measurement requests with zero errors, timeouts, or generator drops and 100% CPU-sample coverage. Tuned HPA used the least capacity in this single run (990.000 pod-seconds), followed by soft HPA (1185.000) and Holt–Winters (1342.499). The latency differences are sub-millisecond at p95 and should not be treated as practically or causally established from one ordered run.

The independent watchdog completed without an abort: 809 watchdog samples; peak load1 3.594, peak CPU 33.605%, minimum available RAM 10.804 GiB, peak swap 0.000 MiB, zero full memory PSI, and zero full I/O PSI. Every arm's separate affinity monitor passed and retained per-thread/descendant observations on CPUs 4–5 plus the unchanged CPU, memory, swap, and PID scope limits.

This is a single-repeat comparison, so it has no variance estimate or significance test. Controller order was fixed prospectively rather than randomized. Logical CPU separation is verified, but CPUs 4–5 share physical cores with kind CPUs 0–1. These guarded 10–45 RPS outcomes are a distinct experiment and are not repetitions of the unsafe 20–120 RPS attempt.
