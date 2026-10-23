# Alibaba comparison preflight

Captured: `2026-10-23T15:42:58.272281+00:00`

Decision: **PASS**.

## Checks

- PASS: `node_ready`
- PASS: `all_existing_pods_running`
- PASS: `metrics_api_available`
- PASS: `phpa_operator_ready`
- PASS: `no_active_benchmark_controller`
- PASS: `workload_endpoint_idle_healthy`
- PASS: `free_disk_above_1_gib`

No image was downloaded and no cluster was created. The existing application, resources, replica limits, timeout, probes, controllers, and collector were retained.

Collector difference: Alibaba runs retain explicit command status, response classification, duration, and stderr diagnostics. This is richer than the accepted NASA runs, so collector-derived availability classifications are not assumed directly comparable without qualification.
