# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/alibaba_first_comparison/alibaba/repeat1/calibrated_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 14900 total (14420 measurement and 480 warmup).
- Records: 14900 total and 14420 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 14420; failures: 0; scheduled-denominator error rate: 0.000000000.
- HTTP failures: none. Client exceptions by class: none. Timeouts: 0; connection failures: 0; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000759549/0.001737896/0.002144647 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007221130/0.008282595/0.011536869 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.982889771 s; offered rate: 34.333333333 requests/s; dispatch-span rate: 34.335353943 requests/s; peak in-flight: 3.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 84 samples, 84 with CPU data, a 5.000473 s maximum gap, and 0.961310 mean per-pod CPU coverage. Mean observed pod CPU was 81.250837 mCPU and 0.142857 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→2 at 185.000s (2026-10-23T15:55:31.201473+00:00), 2→3 at 230.000s (2026-10-23T15:56:16.201482+00:00), 3→4 at 290.000s (2026-10-23T15:57:16.201474+00:00). Maximum and final ready replicas were 4 and 4. The collector saw 0 restart and 5 readiness-deficit samples. Events retain 0 readiness-probe and 0 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 3 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
