# Per-run live validation

## Purpose and provenance

This report validates one asynchronous, open-loop trace-derived demand replay. It does not by itself validate or compare other controller arms. Raw evidence is retained in `results/live_trace_phase/stepped_first_comparison/stepped_d1_s62/repeat1/strawman_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 85058 total (84578 measurement and 480 warmup).
- Records: 85058 total and 84578 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 83825; failures: 753; scheduled-denominator error rate: 0.008903024.
- HTTP failures: none. Client exceptions by class: `TimeoutError`: 753. Timeouts: 753; connection failures: 0; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000723792/0.002108274/0.314841280 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.009372504/0.790186462/3.407081159 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 1200.000 s; actual first-dispatch-to-last-completion span: 1199.982270418 s; offered rate: 70.481666667 requests/s; dispatch-span rate: 70.483300373 requests/s; peak in-flight: 443.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting controller in every measurement sample. There were 240 samples, 240 with CPU data, a 5.030044 s maximum gap, and 0.960099 mean per-pod CPU coverage. Mean observed pod CPU was 102.750068 mCPU and 0.112500 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→5 at 150.000s (2026-10-23T20:34:23.570570+00:00), 5→6 at 215.000s (2026-10-23T20:35:28.570561+00:00), 6→7 at 425.000s (2026-10-23T20:38:58.570575+00:00), 7→8 at 545.000s (2026-10-23T20:40:58.570615+00:00), 8→10 at 560.000s (2026-10-23T20:41:13.570601+00:00), 10→20 at 665.003s (2026-10-23T20:42:58.573371+00:00), 20→12 at 770.000s (2026-10-23T20:44:43.570598+00:00), 12→11 at 830.000s (2026-10-23T20:45:43.570675+00:00), 11→19 at 905.000s (2026-10-23T20:46:58.570713+00:00), 19→20 at 920.000s (2026-10-23T20:47:13.570574+00:00), 20→8 at 995.000s (2026-10-23T20:48:28.570701+00:00), 8→4 at 1010.000s (2026-10-23T20:48:43.570603+00:00), 4→3 at 1040.000s (2026-10-23T20:49:13.570584+00:00). Maximum and final ready replicas were 20 and 3. The collector saw 0 restart and 10 readiness-deficit samples. Events retain 34 readiness-probe and 2 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 443 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU availability and per-pod coverage are reported above without imputation. Missing metrics limit controller-performance inference even when other request and replica streams remain valid.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: dispatch_p99_below_100ms.

**Decision: REJECT.** This decision applies only to this run's instrumentation validity. Poor service performance is not itself a rejection criterion.
