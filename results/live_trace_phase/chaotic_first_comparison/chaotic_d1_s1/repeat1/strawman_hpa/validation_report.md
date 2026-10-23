# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/chaotic_first_comparison/chaotic_d1_s1/repeat1/strawman_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 32678 total (32198 measurement and 480 warmup).
- Records: 32678 total and 32198 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 4677; failures: 27521; scheduled-denominator error rate: 0.854742531.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 25, `ServerDisconnectedError`: 105, `TimeoutError`: 27391. Timeouts: 27391; connection failures: 130; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000947850/0.002503341/0.004903014 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.830899004/4.481659000/4.903828685 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.998450151 s; offered rate: 76.661904762 requests/s; dispatch-span rate: 76.665458149 requests/s; peak in-flight: 603.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 84 samples, 78 with CPU data, a 5.001423 s maximum gap, and 0.767063 mean per-pod CPU coverage. Mean observed pod CPU was 421.611256 mCPU and 0.935897 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→5 at 305.000s (2026-10-23T21:08:41.802962+00:00), 5→8 at 515.000s (2026-10-23T21:12:11.802968+00:00), 8→9 at 530.000s (2026-10-23T21:12:26.802970+00:00). Maximum and final ready replicas were 9 and 9. The collector saw 18 restart and 68 readiness-deficit samples. Events retain 95 readiness-probe and 44 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 603 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
