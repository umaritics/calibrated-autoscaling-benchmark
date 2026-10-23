# Chaotic comparison preflight

Captured: `2026-10-23T21:03:19.487231+00:00`

Decision: **PASS**.

## Checks

- PASS: `correct_context`
- PASS: `node_ready`
- PASS: `all_existing_pods_running`
- PASS: `metrics_api_available`
- PASS: `workload_pod_metrics_nonempty`
- PASS: `phpa_operator_ready`
- PASS: `no_active_benchmark_controller`
- PASS: `workload_endpoint_idle_healthy`
- PASS: `generator_and_analyzer_available`
- PASS: `free_disk_above_1_gib`
- PASS: `available_memory_above_4_gib`

The existing cluster, application, images, policies, resource bounds, probes, port-forward, metrics collector, and operator were reused unchanged.

## Targeted generator review

The previous stepped soft-HPA rejection was retained and not rerun. Its schedule was exact, had zero generator drops, and failed only the frozen dispatch-p99 threshold (0.315 s). This preflight therefore records host load, available memory, free disk, endpoint health, and metrics health immediately before the new fixed run order. No workload intensity or acceptance threshold was changed.
