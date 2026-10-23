# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/onoff_first_comparison/onoff_d1_s81/repeat1/holtwinters`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 30410 total (29930 measurement and 480 warmup).
- Records: 30410 total and 29930 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 25951; failures: 3979; scheduled-denominator error rate: 0.132943535.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 7, `ServerDisconnectedError`: 20, `TimeoutError`: 3952. Timeouts: 3952; connection failures: 27; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000689462/0.001361791/0.002235783 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.008219442/0.050262085/3.431327153 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.996210009 s; offered rate: 71.261904762 requests/s; dispatch-span rate: 71.263986876 requests/s; peak in-flight: 601.

## Autoscaling observations

The collector saw exactly one `PredictiveHorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 84 samples, 84 with CPU data, a 5.000132 s maximum gap, and 0.913815 mean per-pod CPU coverage. Mean observed pod CPU was 104.708653 mCPU and 0.178571 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→3 at 145.000s (2026-10-23T18:41:35.523403+00:00), 3→5 at 165.000s (2026-10-23T18:41:55.523402+00:00), 5→7 at 205.000s (2026-10-23T18:42:35.523410+00:00), 7→10 at 225.000s (2026-10-23T18:42:55.523416+00:00), 10→11 at 505.000s (2026-10-23T18:47:35.523405+00:00), 11→12 at 515.000s (2026-10-23T18:47:45.523409+00:00), 12→13 at 525.000s (2026-10-23T18:47:55.523445+00:00), 13→14 at 535.000s (2026-10-23T18:48:05.523420+00:00). Maximum and final ready replicas were 13 and 13. The collector saw 3 restart and 17 readiness-deficit samples. Events retain 26 readiness-probe and 9 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 601 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
