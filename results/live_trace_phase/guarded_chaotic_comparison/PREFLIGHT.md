# Guarded chaotic preflight

Decision: **PASS**.

The calibrated kind node is hard-pinned to CPUs 0–3 and limited to 8 GiB RAM, zero swap, and 4096 PIDs. The generator's independently verified transient scope is limited to one CPU on CPUs 4–5, 768 MiB RAM, zero swap, and 512 tasks. This leaves CPUs 4–7 outside kind and more than 10 GiB outside the two hard memory caps for the desktop and OS.

The previous-boot journal contains no conclusive OOM/lockup/I/O evidence, so the two freezes remain unattributed.

## Checks

- PASS: `cpu_capacity_known`
- PASS: `memory_headroom_above_4_gib`
- PASS: `swap_pressure_below_1_gib`
- PASS: `disk_headroom_above_4_gib`
- PASS: `docker_limits_requested_match`
- PASS: `docker_cgroup_limits_actual_match`
- PASS: `cluster_query_healthy`
- PASS: `metrics_server_healthy`
- PASS: `watchdog_present`
- PASS: `no_active_benchmark_runner`
