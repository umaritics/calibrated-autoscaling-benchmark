# Live Kubernetes trace replay results

Collected 0/18 planned production-trace runs and 0/3 exploratory PHPA runs. These are new HTTP requests and real Kubernetes scaling events. Raw logs are retained; failed pilots are separate.

Protocol: [fixed live protocol](../../docs/LIVE_TRACE_PROTOCOL.md). Inputs and caveats: [provenance](data_provenance.json). NASA is a fixed July 1 window; Alibaba is a single container’s relative CPU-demand shape with irregular source intervals compressed into equal replay bins. These are workload-replay experiments, not production-system recreations or proof of generalization across the entire datasets.

## Per-run measurements

NOT MEASURED yet.

Error rate includes HTTP failures, unexpected bodies, timeouts and any generator drops. Latency percentiles use successful requests only; read together with errors. Capacity integrates ready replicas over the exact measurement window, including boundary interpolation from bracketing samples. CPU hot fraction is sample-based, not an SLA.

## Across-repeat means and sample SD

All collected measured runs remain in these tables, including any validity flags. Do not interpret an invalid run as a clean comparison. No statistical significance is claimed with three repeats. SD is across repeated executions of the same trace, not across independent production workloads.

## Paired capacity advantage of Holt–Winters

Positive means HW held fewer ready-pod-seconds than that reactive controller. Negative means the reactive controller held fewer. This is not a latency advantage, and we do not subtract advantages in a way that cancels the predictor.

## Exploratory supplied-PHPA trace replay

NOT MEASURED yet.

## Instrumentation validation

| dataset | repeat | arm | pod_seconds | p95_latency_s | error_rate | p99_dispatch_delay_s | generator_drops | valid | category |
|---|---|---|---|---|---|---|---|---|---|
| nasa | 1 | holtwinters | 562.49903 | 1.75236 | 0.18537 | 4.38366 | 1954 | False | pilot |

The original thread-pool pilot was rejected for queueing/drops. Async-generator validation is retained separately. Check each run’s `summary.json` for individual validity checks and `requests.csv`/`metrics.jsonl` for raw evidence. No failed or incomplete run is silently substituted.

## Limits

Single local kind node, shared host, CPU-bound PHP endpoint, fixed amplitude normalization and time compression, one selected window/container, and three repeats per production condition. Baseline tuning changes several HPA parameters together. No isolated causal attribution to one parameter. These measurements do not reproduce the paper’s NASA/Alibaba forecast-MAPE claim or evaluate its LLM. The existing offline and historical live findings remain separate.
