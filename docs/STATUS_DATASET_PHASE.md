# Dataset phase status

## Completed

- Preserved the original 18 live seasonal/burst runs and their capacity conclusions.
- Extracted both supplied Kaggle datasets under `data/`; excluded raw downloads from Git.
- Added complete offline evaluation: 600 scenarios, six patterns, five forecast variants, two horizons, train-only period selection, per-scenario errors and paired comparisons.
- Added all-42-trace online capacity/data-quality analysis and all-36-entry early-detection comparison. These are authors’ runs, not newly executed live trials.
- Added reproducibility manifests, package versions, methodological documentation and temporal-leakage tests.

## Live extension limitation

The available context `kind-research-cluster` is Kubernetes v1.32.2, not the original Docker Desktop v1.36.1 environment. Read-only inspection found `kube-controller-manager-research-cluster-control-plane` in `CreateContainerError`, no PHPA CRD, and existing unrelated KEDA/scaler workloads. No new controller runs were attempted on this unhealthy, occupied environment. No existing workloads were changed. Offline evaluation and released-data analysis provide the six-pattern extension instead.

Next live milestone: a healthy dedicated cluster with PHPA and metrics-server, then growing/onoff/chaotic/stepped × three controllers × at least three repeats. Use longer windows, record latency, and retain the original HW configuration alongside any corrected-period variant. Offline forecast rankings do not settle the tuned-HPA comparison on these four patterns.

## Remaining evidence gaps

NASA and Alibaba files were not supplied. Acquisition details are in `data/README.md`; preprocessing and paper comparability must be specified before testing the production MAPE claim. No Gemini classifier or exact +37.4% paper comparison was reproduced. No performance/SLA claim is supported by CPU saturation alone.

See `results/dataset_phase/offline_results.md` and `online_results.md` for computed tables, and `docs/reproduction_report.md` for the original-versus-ours comparison. Historical handoff text describes the pre-extension state.
