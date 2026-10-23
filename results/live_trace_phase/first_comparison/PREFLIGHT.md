# First NASA comparison preflight

This preflight was completed before comparison measurements on 2026-10-23. The fixed protocol in `docs/LIVE_TRACE_PROTOCOL.md` remains authoritative.

- Dedicated cluster: `calibrated-live`; Kubernetes client/server v1.32.2; node `Ready`; no node memory, disk, or PID pressure.
- Metrics: metrics-server v0.7.1 returned node and pod CPU values.
- Predictive controller: PHPA v0.13.2 deployment available and its CRD functional.
- Application endpoint: `http://127.0.0.1:18080/index.php` returned `OK!` before the runs.
- Host capacity at preflight: 8 allocatable Kubernetes CPUs, about 19 GiB RAM, 6.0 GiB host-available memory, 6.0 GiB free filesystem space. Free disk is a limitation but is ample for three small text/JSON run directories; no images or datasets need downloading.
- Generator: the already-verified asynchronous open-loop implementation in `scripts/live/run_trace.py`; 2,048 in-flight cap, five-second request timeout, fresh connections, and one row per scheduled request including generator drops and service failures.
- Replay: the predetermined 42-bin NASA July 1, 1995 subset and fixed 90x transformation recorded in `data_provenance.json`; 10 seconds per bin, peak 120 requests/s, 120-second 4 requests/s warmup, and 420-second measurement.
- Frozen workload: `php:8.2-apache`, one initial replica, 1--20 autoscaler bounds, 200m CPU request, 500m CPU limit, 64 MiB memory request, 128 MiB memory limit, and the existing readiness/liveness probes.
- Frozen arms: 50% soft HPA, 70% conservative HPA with documented behavior, and existing Holt--Winters PHPA. Run order was fixed in `run_plan.json` before measurement and was not selected from outcomes.
- Reset: delete every HPA/PHPA and the application deployment; wait for old workload pods to disappear; recreate at one replica. Restart the PHPA operator and create a fresh PHPA CR for the predictive arm.
- Tests: all nine repository tests passed before measurement.

## Probe diagnosis and freeze decision

The retained asynchronous pilot had a complete request schedule, zero generator drops, low dispatch delay, service timeouts/disconnections, probe timeouts, and one liveness-triggered workload restart while underscaled. Connection-refused probe events coincided with pod startup or termination. The probes use the correct path and port and succeed at idle; their timeout failures occur on the same CPU-intensive endpoint under load. This supports genuine application saturation/unavailability, with the liveness restart retained as part of the observed service behavior. It does not demonstrate a path, port, or deployment wiring defect. Therefore no probe, resource, timeout, workload, or algorithm parameter was changed.
