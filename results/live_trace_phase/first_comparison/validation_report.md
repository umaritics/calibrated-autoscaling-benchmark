# Historical per-run analyzer output (superseded)

This file was accidentally emitted for the first run while the three-arm
directory was still being populated. Its calculations below apply only to the
soft-HPA run named in the source path; its pilot wording and scope conclusion do
not describe the completed comparison. Use `RESULTS.md`, `comparison.json`, and
`evidence_manifest.json` for the verified three-controller result. The raw
calculation is retained instead of being silently deleted.

## Purpose and provenance

This pilot tested whether the corrected asynchronous, open-loop replay and five-second Kubernetes collector could retain a deterministic NASA schedule while observing one Holt–Winters PHPA arm. It does not validate the planned three-controller comparison. Raw evidence is retained in `results/live_trace_phase/first_comparison/nasa/repeat1/strawman_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 26583 total (26103 measurement and 480 warmup).
- Records: 26583 total and 26103 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 13117; failures: 12986; scheduled-denominator error rate: 0.497490710.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 4, `ServerDisconnectedError`: 26, `TimeoutError`: 12956. Timeouts: 12956; connection failures: 30; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000761202/0.001947247/0.002409191 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007538818/2.036113286/4.355068739 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.994912386 s; offered rate: 62.150000000 requests/s; dispatch-span rate: 62.151939931 requests/s; peak in-flight: 601.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting HPA in every measurement sample. There were 84 samples, 78 with CPU data, a 5.000045 s maximum gap, and 0.884921 mean per-pod CPU coverage. Mean observed pod CPU was 232.243212 mCPU and 0.423077 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→5 at 305.000s (2026-10-23T13:37:47.941672+00:00), 5→4 at 380.000s (2026-10-23T13:39:02.941643+00:00), 4→6 at 530.000s (2026-10-23T13:41:32.941651+00:00). Maximum and final ready replicas were 6 and 6. Thus “five replicas” is the intermediate 3→5 transition; ten ready replicas is the later/final state. The collector saw 4 restart and 28 readiness-deficit samples. Events retain 19 readiness-probe and 6 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 601 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU samples existed at every collector time, but not every current pod had a metrics-server value (mean per-pod coverage 0.884921). The PHPA log also records transient missing/unknown-pod metrics during startup and scaling. This limits controller-performance inference but does not demonstrate silent loss by the instrumentation.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** The retained evidence is sufficient for the pilot's instrumentation purpose. This is not a NASA performance result or evidence that the three-controller campaign ran.
