# NASA repeat-2/3 preflight

The balanced order was frozen in `run_plan.json` before execution: repeat 2 was
tuned HPA, Holt-Winters, soft HPA; repeat 3 was Holt-Winters, soft HPA, tuned
HPA. It was not changed in response to results.

- The dedicated `calibrated-live` node was `Ready`, with memory, disk, and PID
  pressure all false. Kubernetes client/server was v1.32.2.
- Metrics-server returned node and pod CPU. PHPA v0.13.2 and the application
  deployment were both 1/1 ready.
- Exactly one PHPA owned the application at preflight, matching Task 2's final
  state. The runner performed the established exclusive reset before every arm.
- The application and PHPA images remained `php:8.2-apache` and
  `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`.
- `data/live_traces/nasa.csv` and all three repeat-1 copies shared SHA-256
  `9608c0f2c803af80d5247c74d7466dc502718d5e8b01565ecf4e39e40abc8aaf`.
- Free filesystem space was 6.0 GiB before execution and 5.9 GiB afterward.
  The wrapper enforced a 1 GiB stop guard. No unrelated data was deleted.
- All 10 repository tests passed before execution.

The control-plane static pods displayed 0/1 readiness, but the node, API,
scheduler, metrics API, workload, and PHPA operator were functional. This host
/kind reporting anomaly is retained as an environment limitation.
