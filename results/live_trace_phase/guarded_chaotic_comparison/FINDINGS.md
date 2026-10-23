# Guarded chaotic milestone findings

Status: **BLOCKED before research execution**.

The host/resource preflight passed and actual kind limits were verified (CPUs 0–3, 8 GiB RAM, zero swap, 4096 PIDs). The third smoke attempt sent all 90 low-intensity measurement requests successfully, retained 25 watchdog samples, and kept the host responsive: maximum load1 1.957, maximum CPU 11.835%, minimum available RAM 11.112 GiB, zero swap, and zero full memory/I/O PSI.

The generator scope proved its one-CPU quota, 768 MiB memory maximum, zero swap, and 512-task maximum. It did not expose the requested `cpuset.cpus.effective=4-5` value during the smoke, so the predeclared all-limits-match gate failed. No research arm was launched, no QoS/capacity/controller comparison is valid, and no retry or silent weakening occurred.

Smoke attempt 1 was safely aborted by a reset-phase false positive and preserved; the defect was fixed and explicitly resolved. Attempt 2 completed but its final result was not yet visible to the calling channel, so attempt 3 was started and independently produced the same limit-verification failure. Both are preserved; no research arm was retried or started.

The new 10–45 RPS variant remains frozen but unexecuted. It is not comparable as a replicate of the prior 20–120 RPS hazardous run and must never be pooled with it as n=2.
