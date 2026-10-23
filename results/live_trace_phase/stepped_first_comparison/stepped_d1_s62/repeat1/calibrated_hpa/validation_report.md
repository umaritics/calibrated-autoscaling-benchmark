# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/stepped_first_comparison/stepped_d1_s62/repeat1/calibrated_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 85058 total (84578 measurement and 480 warmup).
- Records: 85058 total and 84578 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 69713; failures: 14865; scheduled-denominator error rate: 0.175754924.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 4, `ServerDisconnectedError`: 28, `TimeoutError`: 14833. Timeouts: 14833; connection failures: 32; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000679804/0.001529150/0.002229560 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007761199/0.011010267/2.441518085 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 1200.000 s; actual first-dispatch-to-last-completion span: 1199.979507295 s; offered rate: 70.481666667 requests/s; dispatch-span rate: 70.483318383 requests/s; peak in-flight: 386.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 240 samples, 234 with CPU data, a 5.002217 s maximum gap, and 0.969048 mean per-pod CPU coverage. Mean observed pod CPU was 156.839933 mCPU and 0.217949 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→4 at 305.000s (2026-10-23T19:52:34.739829+00:00), 4→6 at 560.000s (2026-10-23T19:56:49.739857+00:00), 6→7 at 695.000s (2026-10-23T19:59:04.739845+00:00), 7→5 at 1235.000s (2026-10-23T20:08:04.739856+00:00), 5→3 at 1250.000s (2026-10-23T20:08:19.739874+00:00), 3→2 at 1295.000s (2026-10-23T20:09:04.739866+00:00). Maximum and final ready replicas were 7 and 2. The collector saw 3 restart and 28 readiness-deficit samples. Events retain 38 readiness-probe and 13 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 386 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
