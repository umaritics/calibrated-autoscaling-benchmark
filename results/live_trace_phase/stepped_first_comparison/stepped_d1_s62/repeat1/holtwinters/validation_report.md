# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/stepped_first_comparison/stepped_d1_s62/repeat1/holtwinters`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 85058 total (84578 measurement and 480 warmup).
- Records: 85058 total and 84578 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 83725; failures: 853; scheduled-denominator error rate: 0.010085365.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 1, `ServerDisconnectedError`: 3, `TimeoutError`: 849. Timeouts: 849; connection failures: 4; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000665146/0.001175093/0.002098309 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.008107742/0.015670849/1.998763363 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 1200.000 s; actual first-dispatch-to-last-completion span: 1199.978332764 s; offered rate: 70.481666667 requests/s; dispatch-span rate: 70.483381999 requests/s; peak in-flight: 375.

## Autoscaling observations

The collector saw exactly one `PredictiveHorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 240 samples, 240 with CPU data, a 5.000317 s maximum gap, and 0.978109 mean per-pod CPU coverage. Mean observed pod CPU was 63.303590 mCPU and 0.025000 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→5 at 140.000s (2026-10-23T20:12:02.014040+00:00), 5→7 at 205.000s (2026-10-23T20:13:07.014059+00:00), 7→8 at 215.000s (2026-10-23T20:13:17.014027+00:00), 8→10 at 225.000s (2026-10-23T20:13:27.014113+00:00), 10→11 at 565.000s (2026-10-23T20:19:07.014089+00:00), 11→12 at 585.000s (2026-10-23T20:19:27.014063+00:00), 12→13 at 595.000s (2026-10-23T20:19:37.014060+00:00), 13→14 at 605.000s (2026-10-23T20:19:47.014052+00:00), 14→15 at 615.000s (2026-10-23T20:19:57.014063+00:00), 15→14 at 915.000s (2026-10-23T20:24:57.014068+00:00), 14→12 at 935.000s (2026-10-23T20:25:17.014066+00:00), 12→10 at 1215.000s (2026-10-23T20:29:57.014050+00:00), 10→5 at 1235.000s (2026-10-23T20:30:17.014055+00:00), 5→3 at 1245.000s (2026-10-23T20:30:27.014067+00:00). Maximum and final ready replicas were 15 and 3. The collector saw 0 restart and 11 readiness-deficit samples. Events retain 6 readiness-probe and 2 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 375 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
