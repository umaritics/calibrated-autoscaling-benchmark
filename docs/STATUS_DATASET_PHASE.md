# Dataset phase status

## Completed

- Preserved the original 18 live seasonal/burst runs and their capacity conclusions.
- Extracted both supplied Kaggle datasets under `data/`; excluded raw downloads from Git.
- Added complete offline evaluation: 600 scenarios, six patterns, five forecast variants, two horizons, train-only period selection, per-scenario errors and paired comparisons.
- Added all-42-trace online capacity/data-quality analysis and all-36-entry early-detection comparison. These are authors’ runs, not newly executed live trials.
- Added reproducibility manifests, package versions, methodological documentation and temporal-leakage tests.
- Executed and independently verified a NASA-derived live replay: three accepted
  soft-HPA runs, three accepted Holt–Winters runs, and two accepted tuned-HPA
  runs. Two additional tuned-HPA attempts are retained as `INCONCLUSIVE` under
  the unchanged 90% CPU-telemetry rule.
- Validated the bounded Alibaba v2018 prefix and executed one accepted live run
  for each controller on one frozen `c_1`-derived observation-sequence replay.
- Executed one accepted run per controller on a frozen D1 growing-pattern
  replay. Independent verification passed exact schedule/request accounting,
  source/replay hashes, controller exclusivity, CPU coverage, latency
  populations, failure denominators, and pod-second integration.

## Current live extension status

The dedicated `calibrated-live` kind cluster (Kubernetes v1.32.2) was healthy
for the NASA and Alibaba-derived milestones. It is not the original Docker
Desktop v1.36.1 environment. The Alibaba comparison reused the same application,
resources, probes, replica bounds, timeout, controllers, and asynchronous
generator. Its collector adds explicit command/availability diagnostics, so
availability classifications are not assumed directly comparable to older NASA
fields without qualification.

Recommended next milestone: predeclare and execute the stepped-pattern
three-controller comparison using the unchanged application, policies,
acceptance thresholds, and independent-verification framework.

## Remaining evidence gaps

The NASA and Alibaba live replays are benchmark demand transformations, not a
reproduction of the paper's forecast-MAPE protocol. The Alibaba prefix is not a
full or representative dataset sample, and its irregular source timing is not
preserved. No Gemini classifier or exact +37.4% paper comparison was reproduced.

See `results/dataset_phase/offline_results.md` and `online_results.md` for computed tables, and `docs/reproduction_report.md` for the original-versus-ours comparison. Historical handoff text describes the pre-extension state.

## Source provenance follow-up

The original evaluation used the supplied `data.zip`, not a new web download. Following the provenance review, both Kaggle archives were independently downloaded: all 1,288 files match the original supplied inputs byte-for-byte. See `results/dataset_phase/kaggle_source_verification.json` and `scripts/verify_kaggle_sources.py`. This closes the Kaggle source-identity gap. Production-derived live replay now exists, but full-dataset representativeness and exact-paper-protocol gaps remain open. The broader project is not complete.
