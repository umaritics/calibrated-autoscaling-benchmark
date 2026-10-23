# Asynchronous NASA pilot validation

## Purpose and provenance

This pilot tested whether the corrected asynchronous, open-loop replay and five-second Kubernetes collector could retain a deterministic NASA schedule while observing one Holt–Winters PHPA arm. It does not validate the planned three-controller comparison. Raw evidence is retained in `results/live_trace_phase/pilot_async/nasa/repeat1/holtwinters`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 11021 total (10541 measurement and 480 warmup).
- Records: 11021 total and 10541 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 6469; failures: 4072; scheduled-denominator error rate: 0.386301110.
- HTTP failures: none. Client exceptions by class: `ServerDisconnectedError`: 8, `TimeoutError`: 4064. Timeouts: 4064; connection failures: 8; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000717121/0.001983204/0.003745139 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007748092/2.868606572/4.640024529 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 120.000 s; actual first-dispatch-to-last-completion span: 119.996081134 s; offered rate: 87.841666667 requests/s; dispatch-span rate: 87.852456068 requests/s; peak in-flight: 601.

## Autoscaling observations

The collector saw exactly one `PredictiveHorizontalPodAutoscaler` and no conflicting HPA in every measurement sample. There were 24 samples, 24 with CPU data, a 5.007277 s maximum gap, and 0.714881 mean per-pod CPU coverage. Mean observed pod CPU was 244.481417 mCPU and 0.750000 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→3 at 140.000s (2026-10-20T21:49:51.355267+00:00), 3→5 at 160.000s (2026-10-20T21:50:11.355268+00:00), 5→7 at 205.000s (2026-10-20T21:50:56.355299+00:00), 7→10 at 225.000s (2026-10-20T21:51:16.355275+00:00). Maximum and final ready replicas were 10 and 10. Thus “five replicas” is the intermediate 3→5 transition; ten ready replicas is the later/final state. The collector saw 1 restart and 12 readiness-deficit samples. Events retain 22 readiness-probe and 7 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 601 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU samples existed at every collector time, but not every current pod had a metrics-server value (mean per-pod coverage 0.714881). The PHPA log also records transient missing/unknown-pod metrics during startup and scaling. This limits controller-performance inference but does not demonstrate silent loss by the instrumentation.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** The retained evidence is sufficient for the pilot's instrumentation purpose. This is not a NASA performance result or evidence that the three-controller campaign ran.
