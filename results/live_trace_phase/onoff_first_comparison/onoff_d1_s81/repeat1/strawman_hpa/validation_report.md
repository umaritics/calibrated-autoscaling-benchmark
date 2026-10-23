# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/onoff_first_comparison/onoff_d1_s81/repeat1/strawman_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 30410 total (29930 measurement and 480 warmup).
- Records: 30410 total and 29930 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 14951; failures: 14979; scheduled-denominator error rate: 0.500467758.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 1, `ServerDisconnectedError`: 15, `TimeoutError`: 14963. Timeouts: 14963; connection failures: 16; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000708686/0.001599327/0.002234176 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007847668/1.456245742/4.307083563 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.996062730 s; offered rate: 71.261904762 requests/s; dispatch-span rate: 71.263817160 requests/s; peak in-flight: 600.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 84 samples, 78 with CPU data, a 5.000051 s maximum gap, and 0.827679 mean per-pod CPU coverage. Mean observed pod CPU was 270.519358 mCPU and 0.576923 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→5 at 320.000s (2026-10-23T18:25:43.493754+00:00), 5→10 at 350.000s (2026-10-23T18:26:13.493747+00:00), 10→5 at 425.000s (2026-10-23T18:27:28.493733+00:00), 5→3 at 440.000s (2026-10-23T18:27:43.493731+00:00), 3→6 at 470.000s (2026-10-23T18:28:13.493741+00:00), 6→8 at 485.000s (2026-10-23T18:28:28.493750+00:00), 8→10 at 530.000s (2026-10-23T18:29:13.493729+00:00). Maximum and final ready replicas were 10 and 10. The collector saw 3 restart and 33 readiness-deficit samples. Events retain 19 readiness-probe and 6 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 600 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
