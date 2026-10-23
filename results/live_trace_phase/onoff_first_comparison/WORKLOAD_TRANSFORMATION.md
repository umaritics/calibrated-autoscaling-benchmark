# On/off dataset provenance and frozen replay

Frozen before any controller execution.

The preferred D2 online release under `data/workloads-predictional-scaling-patterns/kaggle/kaggle/data/patterns/onoff` was inspected first. Its seven CSVs contain controller decisions, replica state, CPU telemetry, and cumulative scaling history. They contain no request-count or request-rate field and therefore are not replayed as incoming demand.

The replay source is `data/phpa/phpa-datasets/onoff_81_min_pods20_max_pods60_on_duration4_off_duration4_transition_typesharp_transition_noise0.3_test.csv` (SHA-256 `f0e97b4b9713de7c9e565f0a702ad6068c83c02f11d58492d5247cd59526736b`). It has 672 genuine released synthetic observations with columns `timestamp` and `pod_count`, sampled every 15 minutes. `pod_count` is a simulated pod-count demand proxy—not observed HTTP demand, utilization, or measured replicas from a live service. The complete test split spans 168 hours.

Scenario 81 is the lowest numeric identifier in the shortest balanced, sharp-transition subgroup (`on_duration4`, `off_duration4`). The frozen window is the first 42 chronological test observations. Its three visible segments are high (indices 0–15, median 59.0), low (16–31, all 20), and high (32–41, median 68.0); boundaries are source indices 16 and 32. Thus the measurement includes one high→low and one low→high transition without outcome-based window selection.

Each 15-minute interval is replayed for 10 seconds, a constant 90× compression, so this is explicitly a **derived workload**. Request rate is `120 × pod_count / 78`, where 78 is the frozen window maximum and 120 requests/s is the existing live protocol peak. No smoothing, imputation, rearrangement, or per-controller adjustment occurs. The measurement schedule has 29930 requests over 420 seconds, preceded by the established 120-second, 4 requests/s warmup. All arms use the same trace hash `22a26e62ff26d2f8511e30313dd7d07498053e17eb496dbb7ff1982be0a4c3e3`.

Neither HPA sees future demand. The PHPA sees Kubernetes CPU history only. Compression changes the physical time scale and the source variable is a pod-demand proxy mapped to benchmark HTTP traffic, so results do not reproduce the authors' online experiment or represent production service latency.
