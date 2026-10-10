# Initial reproduction report

## Paper
- Title: From Reactive to Predictive: A Pattern-Aware Framework for Kubernetes Autoscaling with Large Language Model Integration
- Authors: Canberk Duman, Süleyman Eken
- Venue: Journal of Systems and Software, vol. 237, 2026
- DOI: https://doi.org/10.1016/j.jss.2026.112861
- GitHub (experiment harness): https://github.com/syswe/workloads-predictional-scaling-operators
- Kaggle (online pattern results): https://www.kaggle.com/datasets/cnbrkdmn/workloads-predictional-scaling-patterns
- Operator actually used: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`

## Problem being addressed
Kubernetes HPA adds pods only after CPU is already high. The paper adds predictive autoscaling (PHPA) with pattern-aware forecasting and LLM-based pattern recognition.

## Core method we implemented
We did **not** re-run the LLM classifier, the 600-scenario offline accuracy study, or all 42 online scenarios. We ran the **online core**: `php-apache` (CPU request 200m), busybox load generator, metrics-server, the authors’ HPA settings (CPU target 50%, scale-down stabilization 60s, max 20), and Holt–Winters with the paper’s coefficients (α=0.9, β=0.2, γ=0.3, seasonalPeriods 6, syncPeriod 10s).

## Cloud computing component
Kubernetes schedules pods. HPA / PHPA change php-apache replicas. metrics-server is the metric pipeline. Docker Desktop Kubernetes (kind, 1 node, v1.36.1). No commercial cloud account.

## Multimodal component
None in our runs. The paper’s LLM path is multimodal text analysis of workloads; we did not call Gemini.

## Dataset
- Synthetic patterns in `generate_pattern_load.py`: **seasonal**, **burst** (deterministic).
- Collection: ~120 s after 30 s warmup, ~5 s samples (row counts 17–21 under load).
- Not used here: NASA HTTP logs, Alibaba Cluster Trace, Gemini labels, full six-pattern matrix.

## Environment
- Host: Windows 10 + WSL2 Ubuntu 24.04 (`Ubuntu2404`), Docker Desktop Engine ~29.x, ~8 GB / 8 CPUs to Docker
- Node: `desktop-control-plane`, Kubernetes v1.36.1, containerd 2.3.1
- Python 3.12.3; kubectl v1.37.1; Helm v3.22.0
- Settings: `RUN_DURATION=120`, `WARMUP_DURATION=30`, `SAMPLING_INTERVAL=5` (authors’ Makefile defaults 300 / 60)

## Original results vs reproduced results

Paper abstract / body emphasise forecast accuracy and LLM classification. Online early-detection numbers appear in the authors’ **Kaggle** release (not as pod-seconds in the abstract). Our primary reproduced metric is **pod-seconds** (capacity), mean ± SD over 3 repeats.

| Result | Original / published | Our result | Notes |
|---|---|---|---|
| HW early detection vs HPA, seasonal | **30.8 s** earlier (Kaggle online release) | NOT RECOMPUTED | Shortened window; we report capacity instead |
| HW early detection vs HPA, burst | **20.5 s** earlier (Kaggle) | NOT RECOMPUTED | Same |
| Gemini pattern classification | **96.7%** (paper abstract) | NOT MEASURED | No LLM API call |
| Pattern-specific vs single-model forecast accuracy | **+37.4%** (paper abstract) | NOT MEASURED | Offline 600-scenario study not re-run |
| Gradient boosting MAPE on NASA / Alibaba | **sub-2%** (paper abstract) | NOT MEASURED | Datasets not downloaded |
| seasonal pod-seconds, strawman HPA | not in abstract | **943.01 ± 94.07** | Our metric |
| seasonal pod-seconds, Holt–Winters | not in abstract | **766.80 ± 39.61** | Our metric |
| seasonal pod-seconds, tuned HPA 70% | N/A (our addition) | **583.25 ± 79.59** | Our metric |
| burst pod-seconds, strawman HPA | not in abstract | **1088.25 ± 274.75** | High variance |
| burst pod-seconds, Holt–Winters | not in abstract | **728.38 ± 46.49** | Our metric |
| burst pod-seconds, tuned HPA 70% | N/A (our addition) | **653.40 ± 24.74** | Our metric |

Full tables, paired differences, Cohen’s d: [`results/results.md`](../results/results.md).

## Possible explanations for differences
Online early-detection was not recomputed (different window/hardware). Pod-seconds are our evaluation addition for the capacity gap question. Holt–Winters state starts empty each arm; `seasonalPeriods=6` implies a 60 s season vs ~80 s seasonal load period — cold-start / mismatch risk.

## Installation problems
1. `docker pull syswe/predictive-horizontal-pod-autoscaler:latest` failed (image not public). Installed `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2` via Helm; adapted CR to `jamiethompson.me/v1alpha1` with the same HW coefficients.
2. Docker CLI not integrated into `Ubuntu2404` WSL; images pulled from Windows; kubectl from WSL used Docker Desktop kubeconfig.
3. metrics-server needed an explicit host pull of `registry.k8s.io/metrics-server/metrics-server:v0.7.1`.

## Missing resources
syswe Docker Hub image; Gemini API (not used); NASA/Alibaba (not used for this deliverable).

## Code problems
`quick_test.sh` is interactive and does not write CSVs — unused. Wrapper uses `run_pattern_tests.sh`.

## Dataset problems
None for seasonal/burst (deterministic).

## Computational limitations
18 arms ≈ 70 minutes. Did not run 6×7 matrix or offline 600 scenarios.

## Deviations from the original experiment
- 2 patterns (not 6); 3 controllers including our tuned HPA.
- 120 s / 30 s warmup (not 300 / 60).
- jthomperoo operator instead of missing syswe image.
- No LLM, no offline MAPE, no NASA/Alibaba.
- Primary metric: pod-seconds + hot fraction (cost/capacity), not early-detection or forecast MAPE.
