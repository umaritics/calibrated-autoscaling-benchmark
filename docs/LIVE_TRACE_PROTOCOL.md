# Live trace replay protocol (fixed before measured runs)

## Objective

Run the existing three-controller comparison on real Kubernetes using NASA and Alibaba-derived demand. Preserve prior offline results as separate evidence. The controllers are the existing 50% HPA, conservative 70% HPA, and Holt–Winters PHPA; no unimplemented adaptive switch is claimed.

## Data and selection

`data_provenance.json` records exact sources, hashes, selections and transformations. NASA uses the first 42 fifteen-minute bins on July 1, 1995. Alibaba uses the first 42 chronological observations of the first named container `c_1`, extracted completely from a 16 MiB HTTP range of the official 29 GB compressed archive. This is a deliberately small, nonrepresentative container subset. Missing container IDs preceding it are counted, not treated as c_1. No outcome-based window selection.

Each value drives ten seconds of HTTP load, normalized to a peak 120 requests/s. NASA compresses source time 90×. Alibaba’s irregular observations become equal replay intervals: this is demand-shape replay, not faithful event-time recreation or the original Alibaba application. No latency claim about NASA or Alibaba production services is possible. A PHPA seasonal_1 trace is an additional exploratory live sanity check, separate from the repeated production-trace matrix.

## Cluster and workload

Dedicated kind cluster `calibrated-live`, Kubernetes v1.32.2, separate kubeconfig. Measured runs use matching kubectl v1.32.2; the preliminary pilot used the host client v1.37. Existing clusters are not modified. PHPA chart/operator v0.13.2; metrics-server v0.7.1 at 15-second resolution. Existing CPU-bound PHP endpoint, CPU request 200m and limit 500m, 1–20 replicas. Record actual resolved image digests. Host has 8 CPUs and about 19 GiB RAM; other host activity remains a limitation and load averages are logged.

## Arms and repeats

NASA and Alibaba: three repeats × three arms = 18 measured runs. Each run has 120 seconds of constant 4 requests/s warmup followed by 420 seconds of trace replay. This exceeds the tuned baseline’s 300-second scale-down window. Rotate arm order across repeats using a Latin square; alternate dataset order. Exploratory PHPA seasonal check: one run per arm, 120-second warmup and 180-second replay; report separately without SD.

Task 5 deliberately stops before that broader Alibaba campaign. Its bounded
milestone executes exactly one Alibaba-derived run per controller in the fixed
order soft HPA, tuned HPA, Holt–Winters. It reports no between-repeat variance.
The pre-existing three-repeat paragraph remains a future-campaign design, not a
claim about completed Alibaba runs.

Between arms, delete controllers and deployment, wait for old pods to disappear, redeploy at one replica. Restart PHPA process before each predictive arm and create a fresh CR UID. Never install both controllers on the same deployment. Use identical request schedules within each dataset, independent of responses. A pilot is kept outside measured runs; any pilot-driven intensity change must be documented before the main matrix begins.

## Measurement and verification

Open-loop scheduled HTTP requests, an asynchronous HTTP client, up to 2,048 in-flight requests, five-second timeout, and a fresh connection per request. The preliminary 64-thread pilot was rejected for generator queueing/drops; its files are retained under `pilot/`. The measured matrix uses the corrected async generator. Log planned/actual dispatch, completion, response status, latency and errors for every scheduled request. Five-second collector records raw deployment/pod/controller objects, CPU metrics, collection duration and host load. Save events, initial/final objects and operator logs.

Primary measures: ready-pod-seconds over the common measurement window, per-run p50/p95/p99 response latency, error rate, and time fraction above the original 160m per-pod CPU threshold. Report offered versus achieved throughput and dispatch delays to detect generator saturation. Timeouts are errors, not omitted successes. Latency is reported for successful requests separately from timeout/error counts; no measured production SLA is assumed.

Verification must check request count against the deterministic schedule, generator drops and dispatch delay, collector gaps, CPU metric availability, controller exclusivity, observed scaling, pod restarts, and cluster health. Failures remain recorded and are not silently replaced. Repeats produce mean and sample SD across runs, with paired capacity differences. No significance claim from three repeats.

## Reproduction commands

Use a machine with Docker, kind and Helm, enough free space for a node and workload images, and no conflicting port 18080. The bootstrap intentionally fails if `calibrated-live` already exists. It does not replace existing clusters.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-live.txt
bash scripts/live/download_traces.sh
bash scripts/live/bootstrap.sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/live/run_trace.py --dataset nasa --arm holtwinters --category pilot_async --warmup 120 --duration 120
.venv/bin/python scripts/live/analyze_runs.py
# Inspect pilot summary checks before proceeding:
.venv/bin/python scripts/live/run_matrix.py
.venv/bin/python scripts/live/analyze_runs.py
.venv/bin/python scripts/live/report.py
```

The runner refuses to overwrite existing run directories. Matrix resume skips completed runs and stops on an unfinished directory requiring review. Each run records hashes of the replay, policy, application manifest and runner. `execution_ledger.jsonl` records every matrix subprocess return code; `run_plan.json` fixes the order before execution. Raw downloads and kubeconfig remain untracked.
