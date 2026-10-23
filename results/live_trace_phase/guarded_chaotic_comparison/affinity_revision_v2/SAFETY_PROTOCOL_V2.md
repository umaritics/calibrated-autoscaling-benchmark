# Guarded chaotic safety protocol v2 — scheduler-affinity read-back

Frozen prospectively: 2026-10-24, before smoke attempt 4 and before every research arm.

## Scope and reason for revision

Task 12's smoke attempt 3 remains **FAILED** under protocol v1. Its live transient
scope was correctly identified, but the user slice delegated only the `memory` and
`pids` controllers, not `cpuset`. Therefore `AllowedCPUs=4-5` appeared in systemd,
while `EffectiveCPUs` was empty and the live scope had no
`cpuset.cpus.effective` file. Protocol v1 correctly refused to infer a value from a
missing file. Nothing in this revision retroactively accepts that smoke.

Protocol v2 uses Linux scheduler affinity as the CPU-set enforcement mechanism.
The generator scope is launched through `taskset --cpu-list 4-5`; the kernel's
`sched_getaffinity(2)` result and `/proc/<pid>/task/<tid>/status` are independently
read for the wrapper, generator, every observed generator thread, and every
observed descendant. A dedicated child probe must independently inherit `[4,5]`.
Any observation outside CPUs 4–5 fails closed and stops the current run. The live
scope's `cpu.max`, `memory.max`, `memory.swap.max`, and `pids.max` must still equal
`100000 100000`, `805306368`, `0`, and `512` respectively.

`AllowedCPUs=4-5` remains requested as defence in depth and must be recorded, but
neither it nor a configuration assertion substitutes for scheduler read-back.
The absent cgroup cpuset file is recorded explicitly; it is never treated as a
successful cpuset observation.

## CPU topology and isolation claim

CPUs 0–7 are online. Kind is independently pinned to logical CPUs 0–3. Logical
CPUs 4–5 are SMT siblings of CPUs 0–1 (cores 0 and 1), so this mechanism provides
logical-CPU separation, **not physical-core isolation**. The generator also keeps
its one-CPU quota. This limitation is part of the interpretation.

## Unchanged gates

- Kind: CPUs 0–3, 8 GiB memory, zero swap, 4096 PIDs.
- Generator: CPUs 4–5 scheduler mask, one-CPU quota, 768 MiB memory, zero swap,
  512 tasks, and 256 maximum in-flight requests (32 in the low-intensity smoke).
- Independent watchdog: unchanged two-second sampling, three sustained samples,
  host load/CPU/memory/PSI/swap/disk thresholds, generator in-flight threshold,
  workload readiness check, process-group termination, evidence preservation,
  and matrix-wide stop latch.
- Frozen workload: 120-second warmup, 420-second measurement, five-second request
  timeout, 12,532 measurement requests, and schedule SHA-256
  `79db2b7c2e8ca93c3f40dcfed88154a7da76eb66e8a6686a69ced4d05096639d`.
- Scientific acceptance: complete schedule, zero generator drops, dispatch p99
  below 0.1 s, CPU coverage at least 0.9, maximum metric gap below 15 s,
  controller exclusivity, bracketed measurement window, and observed scaling.

## Prospective decision rule

Smoke attempt 4 may pass only if scheduler affinity, every other actual resource
limit, valid requests, metrics, watchdog telemetry, host-pressure thresholds,
and cleanup all pass. The research orchestrator may run only if that smoke result
records this file's SHA-256. During each arm, the independent affinity monitor and
watchdog remain active. An affinity/resource/watchdog violation classifies the arm
`SAFETY_ABORTED`, preserves partial evidence, and blocks all remaining arms.
