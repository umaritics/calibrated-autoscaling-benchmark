# Historical per-run analyzer output (superseded)

This file was accidentally emitted when this directory temporarily contained a
single run. Its calculations below apply only to the tuned-HPA repeat-2 run
named in the source path; its pilot wording and scope conclusion do not describe
the repetition checkpoint. Use `independent_verification.json`,
`nine_run_summary.json`, `FINDINGS.md`, and `evidence_manifest.json` for the
verified partial matrix. The raw calculation is retained instead of being
silently deleted.

## Purpose and provenance

This pilot tested whether the corrected asynchronous, open-loop replay and five-second Kubernetes collector could retain a deterministic NASA schedule while observing one Holt–Winters PHPA arm. It does not validate the planned three-controller comparison. Raw evidence is retained in `results/live_trace_phase/nasa_three_repeat/nasa/repeat2/calibrated_hpa`; source paths and SHA-256 hashes are recorded in `summary.json`, with run-time input hashes also retained in the run's `metadata.json`.

## Recomputed request measurements

- Deterministic schedule: 26583 total (26103 measurement and 480 warmup).
- Records: 26583 total and 26103 measurement; missing 0, unexpected 0, duplicate 0.
- Measurement successes: 15817; failures: 10286; scheduled-denominator error rate: 0.394054323.
- HTTP failures: none. Client exceptions by class: `ClientOSError`: 3, `ServerDisconnectedError`: 39, `TimeoutError`: 10244. Timeouts: 10244; connection failures: 42; cancellations: 0; generator drops: 0.
- Dispatch delay p50/p95/p99: 0.000770855/0.001969370/0.002268704 s. The 100 ms p99 threshold comes from the fixed protocol.
- Successful-request latency p50/p95/p99: 0.007276194/2.024587866/4.475158585 s. Failures are excluded only from latency and remain in the error denominator.
- Intended replay duration: 420.000 s; actual first-dispatch-to-last-completion span: 419.995478711 s; offered rate: 62.150000000 requests/s; dispatch-span rate: 62.151741746 requests/s; peak in-flight: 601.

## Autoscaling observations

The collector saw exactly one `HorizontalPodAutoscaler` and no conflicting HPA in every measurement sample. There were 84 samples, 84 with CPU data, a 5.000797 s maximum gap, and 0.876984 mean per-pod CPU coverage. Mean observed pod CPU was 223.932006 mCPU and 0.440476 of CPU samples exceeded the protocol's original 160 mCPU threshold. Desired transitions were 1→2 at 135.000s (2026-10-23T14:15:36.236018+00:00), 2→3 at 305.000s (2026-10-23T14:18:26.236042+00:00), 3→4 at 530.000s (2026-10-23T14:22:11.236012+00:00). Maximum and final ready replicas were 4 and 4. Thus “five replicas” is the intermediate 3→5 transition; ten ready replicas is the later/final state. The collector saw 4 restart and 29 readiness-deficit samples. Events retain 38 readiness-probe and 12 liveness-probe failures.

## Failure diagnosis and limitations

The generator was not demonstrably overloaded: it retained the complete schedule, had no capacity drops, stayed below the dispatch threshold, and peaked at 601 in flight versus its 2,048 limit. The five-second `TimeoutError` outcomes and short `ServerDisconnectedError` outcomes coincide with readiness/liveness failures and a workload restart while the service was underscaled. This supports service-side overload/unavailability rather than generator queueing as the proximate cause. Requests lack endpoint/pod identity and host telemetry is limited, so ultimate attribution of every timeout remains partly **UNKNOWN**.

CPU samples existed at every collector time, but not every current pod had a metrics-server value (mean per-pod coverage 0.876984). The PHPA log also records transient missing/unknown-pod metrics during startup and scaling. This limits controller-performance inference but does not demonstrate silent loss by the instrumentation.

## Criteria and decision

Predetermined criteria in `docs/LIVE_TRACE_PROTOCOL.md` are deterministic schedule retention, no drops, p99 dispatch delay below 100 ms, gaps below 15 s, above-90% CPU-sample availability, controller exclusivity, a bracketed window, and observed scaling. Timestamp, duplicate, and UTC checks are integrity checks added here, not retroactively claimed numeric thresholds. Failed checks: none.

**Decision: ACCEPT.** The retained evidence is sufficient for the pilot's instrumentation purpose. This is not a NASA performance result or evidence that the three-controller campaign ran.
