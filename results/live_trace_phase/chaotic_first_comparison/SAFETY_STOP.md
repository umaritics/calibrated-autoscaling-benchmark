# Chaotic live comparison safety stop

Status: **BLOCKED — host safety**.

The frozen chaotic comparison was stopped after the Pop!_OS host became unresponsive twice during Holt–Winters execution and required reboot/recovery. No further load is authorized on this host under the frozen protocol. The remaining benchmark PHPA was deleted after the second interruption, leaving no active HPA/PHPA in `trace-benchmark` at cleanup time.

## Completed evidence

The required first arm, soft HPA, completed collection and passed the unchanged analyzer acceptance checks. This means its evidence and instrumentation are valid; it does not mean its QoS was acceptable. It scheduled 32,198 measurement requests, recorded all 32,198, succeeded on 4,677, and failed on 27,521 (85.474253%): 27,391 timeouts and 130 connection failures. Generator drops were zero and dispatch p99 was 0.004903 s. CPU coverage was 92.8571%, ready-pod capacity was 684.995858 pod-seconds, mean/max ready replicas were 1.630943/9, readiness-deficit samples were 68, and workload restarts reached 18.

Successful-request latency p50/p95/p99 was 0.830899/4.481659/4.903829 s. These latency statistics exclude failures and must be read with the 85.47% scheduled-request error rate.

## Interrupted evidence

Two Holt–Winters attempts are retained separately and are not promoted to experiment statistics:

- `interrupted_runs/holtwinters_host_freeze_20261024T0024Z/`: 30,131 request rows plus header and 96 telemetry records; maximum recorded host one-minute load 37.111816.
- `interrupted_runs/holtwinters_host_freeze_20261024T0044Z/`: abruptly truncated request file and 58 telemetry records; maximum recorded host one-minute load 25.416504.

Neither attempt has a `COMPLETE` marker, final objects, events, analyzer summary, or full schedule accounting. Both are therefore incomplete and excluded. Tuned HPA was never started.

## Safety diagnosis

The accepted soft-HPA run recorded a maximum host one-minute load of **106.351562**, peak client concurrency of 603, mean/max observed pod CPU of 421.611/500.731 mCPU, 68 readiness-deficit samples, and 18 workload restarts. This is strong evidence that the live benchmark drove severe host/container scheduler pressure. Current post-reboot memory was healthy (12 GiB available, zero swap used), and the previous-boot kernel log contained no OOM-kill, hung-task, or storage-I/O-error record in the inspected tail. Therefore the exact kernel-level failure mechanism is unresolved; benchmark-induced host overload is the leading explanation, not a proven sole cause.

The filesystem was 94% used with 5.5 GiB free after recovery. This passed the experiment's fixed 1 GiB guard but is an additional operational risk.

## Scientific disposition

- Soft HPA: **ACCEPT** as a single independently analyzable run.
- Holt–Winters: **INCOMPLETE / EXCLUDED** for both interrupted attempts.
- Tuned HPA: **NOT RUN**.
- Three-controller comparison: **BLOCKED**, so no cross-controller or chaotic-specific comparative conclusion is valid.

The workload, trace, order, and acceptance thresholds were not modified after observing results. A lower-rate retry on this host would be a different protocol and is not silently substituted.
