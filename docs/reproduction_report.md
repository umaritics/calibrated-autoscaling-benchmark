# Initial reproduction report

## Paper
- Title: From Reactive to Predictive: A Pattern-Aware Framework for Kubernetes Autoscaling with Large Language Model Integration
- Authors: Canberk Duman, Süleyman Eken
- Venue: Journal of Systems and Software
- Year: 2026
- Paper link: https://doi.org/10.1016/j.jss.2026.112861
- GitHub (experiment harness): https://github.com/syswe/workloads-predictional-scaling-operators
- Operator actually used: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2` (see Installation problems)

## Problem being addressed
Kubernetes HPA adds pods only after CPU is already high. The paper adds a predictive autoscaler so replica count can move before a peak.

## Core method we implemented
We did not re-run the LLM classifier, the 42-scenario matrix, or the offline accuracy study. We ran the online core: `php-apache` (CPU request 200m), a busybox load generator, metrics-server, the authors’ HPA settings (CPU target 50%, scale-down stabilization 60s, max 20), and Holt–Winters with the paper’s parameters (alpha 0.9, beta 0.2, gamma 0.3, seasonalPeriods 6, additive trend and season, syncPeriod 10s).

## Cloud computing component
Kubernetes schedules the pods. HPA and the PHPA operator change the php-apache replica count. metrics-server is the metric pipeline. Docker Desktop Kubernetes (kind, 1 node, v1.36.1) is the cluster. No commercial cloud account was used.

## Multimodal component
None. The workload is HTTP requests that consume CPU. There is no text, image, audio, or video model.

## Dataset
- Name: synthetic patterns in `scripts/generate_pattern_load.py`
- Source: the authors’ repository, functions `seasonal_pattern` and `burst_pattern`
- Modality: a time series of desired load-generator replica counts, which produces CPU load on php-apache
- seasonal: sine wave, base 4, amplitude 12, period 80 seconds, about 4–16 replicas. Deterministic.
- burst: base 4, peaks of 18 at t = 30, 100, 180, and 260 seconds, duration 25 seconds. Deterministic.
- Samples: one generated trace per run, collected every 5 seconds for 120 seconds after a 30-second warmup
- Split: not a train/validation/test split. Holt–Winters updates online inside the operator.
- Preprocessing: none beyond the authors’ scripts
- Filtering / augmentation: none
- Not used: Azure Public Dataset, NASA HTTP logs, Alibaba cluster trace, Gemini labels

## Environment
- Operating system: Linux Umars-850-G6 6.18.40.1-microsoft-standard-WSL2 (Ubuntu 24.04 WSL2 distro `Ubuntu2404`), host Windows 10
- Kubernetes node: `desktop-control-plane`, Ready, control-plane, v1.36.1, Debian 13, containerd 2.3.1
- Docker Desktop: Engine 29.6.2, ~8 GB RAM / 8 CPUs allocated to Docker
- Python: 3.12.3
- kubectl: v1.37.1
- Helm: v3.22.0
- Libraries in the venv: numpy, pandas, matplotlib, statsmodels
- Not installed on purpose: catboost, xgboost, scikit-learn
- Important settings: `NAMESPACE=phpa-lab`, `RUN_DURATION=120`, `WARMUP_DURATION=30`, `SAMPLING_INTERVAL=5`
- Deviation from the authors’ Makefile defaults: they use `RUN_DURATION=300` and `WARMUP_DURATION=60`. We shortened both so three repeats could finish on a student laptop before the deliverable deadline.

## Original results vs reproduced results

The authors’ repository README does not publish the numeric online table. Cells that would have been copied from a paper table are `NOT PUBLISHED IN THE REPOSITORY`. Reproduced cells are from `output/our_study/results.md` (mean pod-seconds across 3 repeats).

| Result | Original paper | Reproduced result | Difference |
|---|---|---|---|
| seasonal mean pod-seconds, strawman HPA | NOT PUBLISHED IN THE REPOSITORY | 978.92 | NOT COMPARABLE |
| seasonal mean pod-seconds, Holt–Winters | NOT PUBLISHED IN THE REPOSITORY | 800.11 | NOT COMPARABLE |
| seasonal mean pod-seconds, calibrated HPA (our addition) | N/A (not in paper) | 608.54 | N/A |
| burst mean pod-seconds, strawman HPA | NOT PUBLISHED IN THE REPOSITORY | 1122.98 | NOT COMPARABLE |
| burst mean pod-seconds, Holt–Winters | NOT PUBLISHED IN THE REPOSITORY | 735.51 | NOT COMPARABLE |
| burst mean pod-seconds, calibrated HPA (our addition) | N/A (not in paper) | 668.09 | N/A |
| Gemini pattern-classification accuracy 96.7% | PAPER CLAIM, NOT RE-MEASURED BY US | NOT MEASURED | We did not call an LLM API |
| +37.4% forecast accuracy vs a single model | PAPER CLAIM, NOT RE-MEASURED BY US | NOT MEASURED | We did not run the offline forecast benchmark |
| sub-2% MAPE on NASA and Alibaba | PAPER CLAIM, NOT RE-MEASURED BY US | NOT MEASURED | Those datasets were not downloaded |

## Possible explanations for differences
There is no numeric difference to explain against a published online table. Our window is 120 seconds rather than 300. The cluster is Docker Desktop on a student laptop, not the authors’ machine. The chaotic pattern was not run. Holt–Winters state starts empty on every run because the wrapper deletes the autoscaler between arms. The operator image is the upstream jthomperoo build (see below), not a private `syswe/...` image.

## Installation problems
1. `docker pull syswe/predictive-horizontal-pod-autoscaler:latest` failed with “pull access denied / repository does not exist”. The authors’ README also documents the upstream project. We installed `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2` via the official Helm chart and rewrote `manifests/phpa-holtwinters.yaml` to API group `jamiethompson.me/v1alpha1` with the same Holt–Winters coefficients as the paper’s YAML.
2. Docker CLI was not integrated into the `Ubuntu2404` WSL distro. Images were pulled from Windows PowerShell; kubectl/helm ran from WSL against the Docker Desktop kubeconfig.
3. metrics-server first stuck in `ContainerCreating` until `registry.k8s.io/metrics-server/metrics-server:v0.7.1` was pulled on the host.

## Missing resources
The claimed `syswe/predictive-horizontal-pod-autoscaler` Docker Hub image was missing. Gemini was not used. Azure traces were not required for this core run.

## Code problems
`scripts/quick_test.sh` ends with an interactive `read -p` and does not write a CSV; we did not use it. We used `scripts/run_pattern_tests.sh` via a wrapper. Plot generation warns that `baseline_hpa.csv` is missing because we renamed the strawman output to `strawman_hpa.csv`; this does not affect metrics.

## Dataset problems
NONE for seasonal and burst. Both functions are deterministic.

## Computational limitations
One arm is warmup 30s + collection 120s + reset sleeps (~45s). Eighteen arms took roughly 70 minutes wall-clock. We did not run 6 patterns × 7 models.

## Deviations from the original experiment
- Two patterns instead of six.
- Controllers: strawman HPA, Holt–Winters, plus our calibrated HPA.
- Collection window 120s / warmup 30s instead of 300s / 60s.
- Operator: jthomperoo v0.13.2 with `jamiethompson.me` CRD (authors’ Docker Hub image unavailable).
- No LLM, no offline MAPE, no NASA, no Alibaba.
