# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/growing_first_comparison/growing_d1_s1/repeat1/holtwinters`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 31213 total (30733 measurement and 480 warmup).
- Records: 31213 total and 30733 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 30733; failures: 0; scheduled-denominator error rate: 0.000000000.
- HTTP failures: none. Client exceptions by class: none. Timeouts: 0; connection failures: 0; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000665841/0.001158215/0.002115089 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007685411/0.012463408/0.021323493 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.993450496 s; offered rate: 73.173809524 requests/s; dispatch-span rate: 73.177488087 requests/s; peak in-flight: 10.

## Autoscaling observations

The collector saw exactly one `PredictiveHorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 84 samples, 84 with CPU data, a 5.000379 s maximum gap, and 0.931244 mean per-pod CPU coverage. Mean observed pod CPU was 81.970686 mCPU and 0.035714 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→2 at 150.000s (2026-10-23T19:24:32.063290+00:00), 2→3 at 175.000s (2026-10-23T19:24:57.063263+00:00), 3→4 at 185.000s (2026-10-23T19:25:07.063276+00:00), 4→5 at 195.000s (2026-10-23T19:25:17.063280+00:00), 5→6 at 295.000s (2026-10-23T19:26:57.063239+00:00), 6→7 at 305.000s (2026-10-23T19:27:07.063441+00:00), 7→8 at 315.000s (2026-10-23T19:27:17.063315+00:00), 8→9 at 325.000s (2026-10-23T19:27:27.063274+00:00), 9→10 at 485.000s (2026-10-23T19:30:07.063292+00:00), 10→11 at 495.000s (2026-10-23T19:30:17.063311+00:00), 11→12 at 505.000s (2026-10-23T19:30:27.063267+00:00). Maximum and final ready replicas were 12 and 12. The collector saw 0 restart and 11 readiness-deficit samples. Events retain 0 readiness-probe and 0 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 10 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
