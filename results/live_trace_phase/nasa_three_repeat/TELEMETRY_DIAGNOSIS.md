# NASA CPU telemetry diagnosis and sensitivity analysis

**Root-cause decision: B — demonstrated genuine metrics unavailability, with a reporting weakness that did not create the gaps.**

Every missing collector sample is a successful, parsed `PodMetricsList` response with `items: []` and no API error field. During the affected periods, saved HPA status/events repeatedly report `FailedGetResourceMetric`, including “no metrics returned from resource metrics API” and “did not receive metrics for targeted pods”; three attempt-2 samples instead retain the HPA’s last valid metric status while the direct API response is empty. Collection stayed near 0.1 s and the five-second sampling cadence continued. This rules against a collector command failure as the cause of these observations. The old collector did not separately retain return code/stderr/duration, so it was weaker than ideal for diagnosis; its code only parsed stdout on return code zero, and the API payload plus independent HPA evidence are convergent. The artifacts do not expose metrics-server internals, so the lower-level reason it returned no pod metrics remains unknown.

## Frozen acceptance and selection risk

The 90% minimum is implemented in `scripts/live/analyze_runs.py` as `cpu samples >= 0.9 × measurement samples` (despite the historical check name saying “above”). The fixed protocol requires CPU-availability verification, and the first-comparison verifier calls the analyzer checks predeclared. The strongest timestamped bound is `execution_ledger.jsonl`: it records the first threshold failure at 2026-10-23 15:08:28 UTC, before the unchanged retry began at 15:08:58 UTC. Because the scientific worktree is untracked, Git does not cryptographically establish the threshold’s original creation time. The threshold is retained unchanged: both attempts remain `INCONCLUSIVE`. CPU mean/max, hot-sample fraction, and per-pod metric coverage require CPU observations; request/QoS, ready-pod integration, replicas, and controller identity come from independent saved streams. Excluding low-coverage runs can bias accepted statistics toward healthier service periods because missingness overlaps instability. The overlap is evidence of selection-bias risk, not proof that instability alone caused every gap.

## Missing-sample timeline

| Attempt | UTC | Elapsed (s) | Ready/current/desired | Restarts | HPA metric state | Requests / failures / timeouts in ±2.5 s | Success p95 (s) |
|---|---|---:|---:|---:|---|---:|---:|
| inconclusive_attempt1 | 2026-10-23T15:02:20.015041+00:00 | 175.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 405 / 405 / 405 | NA |
| inconclusive_attempt1 | 2026-10-23T15:02:25.015005+00:00 | 180.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 451 / 451 / 451 | NA |
| inconclusive_attempt1 | 2026-10-23T15:02:30.015016+00:00 | 185.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API | 497 / 497 / 497 | NA |
| inconclusive_attempt1 | 2026-10-23T15:03:05.015000+00:00 | 220.000 | 0/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 320 / 320 / 320 | NA |
| inconclusive_attempt1 | 2026-10-23T15:03:10.015007+00:00 | 225.000 | 0/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 319 / 319 / 319 | NA |
| inconclusive_attempt1 | 2026-10-23T15:03:15.015012+00:00 | 230.000 | 0/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API | 308 / 308 / 308 | NA |
| inconclusive_attempt1 | 2026-10-23T15:03:50.015040+00:00 | 265.000 | 0/1/1 | 3 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 237 / 189 / 189 | 4.909332829049345 |
| inconclusive_attempt1 | 2026-10-23T15:03:55.014965+00:00 | 270.000 | 1/1/1 | 3 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 243 / 208 / 208 | 4.701853224499609 |
| inconclusive_attempt1 | 2026-10-23T15:04:00.016371+00:00 | 275.001 | 1/1/1 | 3 | the HPA was unable to compute the replica count: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API | 247 / 247 / 247 | NA |
| inconclusive_attempt2 | 2026-10-23T15:11:46.963741+00:00 | 160.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 464 / 464 / 464 | NA |
| inconclusive_attempt2 | 2026-10-23T15:11:51.963754+00:00 | 165.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 447 / 447 / 447 | NA |
| inconclusive_attempt2 | 2026-10-23T15:11:56.963730+00:00 | 170.000 | 1/1/1 | 1 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 426 / 426 / 426 | NA |
| inconclusive_attempt2 | 2026-10-23T15:12:31.963723+00:00 | 205.000 | 0/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 415 / 367 / 357 | 4.895949876799477 |
| inconclusive_attempt2 | 2026-10-23T15:12:36.963708+00:00 | 210.000 | 1/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 368 / 368 / 368 | NA |
| inconclusive_attempt2 | 2026-10-23T15:12:41.963743+00:00 | 215.000 | 1/1/1 | 2 | the HPA was unable to compute the replica count: failed to get cpu utilization: did not receive metrics for targeted pods (pods might be unready) | 321 / 321 / 321 | NA |
| inconclusive_attempt2 | 2026-10-23T15:14:16.963737+00:00 | 310.000 | 1/4/4 | 4 | last HPA status still valid or unavailable | 226 / 191 / 191 | 4.710721271500188 |
| inconclusive_attempt2 | 2026-10-23T15:14:21.963755+00:00 | 315.000 | 4/4/4 | 4 | last HPA status still valid or unavailable | 209 / 108 / 108 | 0.04852002500047092 |
| inconclusive_attempt2 | 2026-10-23T15:14:26.963739+00:00 | 320.000 | 4/4/4 | 4 | last HPA status still valid or unavailable | 190 / 46 / 46 | 0.011539194050692458 |

Each timeline row is computed from that run’s `metrics.jsonl` and `requests.csv`; event-level corroboration and replica changes are in `telemetry_diagnosis.json`. Kubernetes event objects are aggregated snapshots, so their counts/timestamps are supporting context rather than a complete transition log.

## Supplementary sensitivity analysis (excluded from accepted statistics)

| Run | Decision | Successes / scheduled | Error rate | Timeouts | Success p95 (s) | Pod-s | Mean/max ready | CPU coverage | Missing bursts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| accepted_tuned_repeat1 | ACCEPT | 16682 / 26103 | 36.092% | 9404 | 2.457239 | 927.499746 | 2.208/4 | 100.000% | none |
| accepted_tuned_repeat2 | ACCEPT | 15817 / 26103 | 39.405% | 10244 | 2.024588 | 902.499649 | 2.149/4 | 100.000% | none |
| inconclusive_attempt1 | INCONCLUSIVE | 12878 / 26103 | 50.665% | 13014 | 2.404539 | 982.499704 | 2.339/4 | 89.286% | 175–185s, 220–230s, 265–275s |
| inconclusive_attempt2 | INCONCLUSIVE | 12490 / 26103 | 52.151% | 13576 | 0.020656 | 1139.999531 | 2.714/5 | 89.286% | 160–170s, 205–215s, 310–320s |

Accepted soft-HPA repeats 1 and 2 also contain six empty samples each (78/84, 92.9%) and remained above the frozen threshold; full cross-controller details are in `telemetry_diagnosis.json`. Thus empty metric bursts were not unique to the excluded tuned-HPA attempts, while both excluded attempts show more missingness and substantial service instability.

## Instrumentation correction

Future collector records now preserve per-command success, return code, redacted/truncated stderr, timeout state, duration, response kind, item count, response size, and an explicit `success` / `empty_response` / `command_failure` / `invalid_json` classification. The analyzer reports availability counts and exact CPU coverage. No workload, controller, probe, replay, or acceptance setting changed; no missing CPU value is imputed. Existing artifacts and decisions were not overwritten.

## Recommendation

**C — retain the partial NASA matrix and proceed to the next handoff workload.** Two unchanged tuned-HPA attempts reproduced the same below-threshold coverage while independently verifiable outcomes show instability. Further retries would invite outcome/availability-based selection, and a replacement run with richer telemetry would not be instrumentation-identical to the accepted series. Start richer collection only as a predeclared future series, not as a selective repair of this matrix.
