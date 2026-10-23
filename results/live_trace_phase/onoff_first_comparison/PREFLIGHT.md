# On/off comparison preflight

Captured: `2026-10-23T18:20:06.423529+00:00`

Decision: **PASS**.

## Checks

- PASS: `node_ready`
- PASS: `all_existing_pods_running`
- PASS: `metrics_api_available`
- PASS: `phpa_operator_ready`
- PASS: `no_active_benchmark_controller`
- PASS: `workload_endpoint_idle_healthy`
- PASS: `free_disk_above_1_gib`
- PASS: `available_memory_above_4_gib`

The existing cluster, application, images, controller policies, resource bounds, probes, port-forward, metrics collector, and operator were reused unchanged.
