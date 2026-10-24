# Local datasets

The supplied `data.zip` was extracted without changing its member paths. Raw files are kept here and ignored by Git; the ZIP is also ignored. The committed `results/dataset_phase/dataset_manifest.csv` identifies all 1,200 D1 files by SHA-256, byte size, row count, and zero count.

- D1: [PHPA Research Datasets](https://www.kaggle.com/datasets/cnbrkdmn/phpa-research-datasets). Place the 1,200 CSVs under `data/phpa/phpa-datasets/`.
- D2: [Workloads Predictional Scaling Patterns](https://www.kaggle.com/datasets/cnbrkdmn/workloads-predictional-scaling-patterns). Preserve the supplied layout `data/workloads-predictional-scaling-patterns/kaggle/kaggle/data/patterns/{pattern}/`. The reader accepts other nesting beneath that dataset folder.

Both supplied READMEs declare MIT licensing. Keep those upstream READMEs with the local downloads. The archive hash is in `results/dataset_phase/environment.json`. `data.zip` includes the `data/` prefix: from the repository root, `unzip -n data.zip` restores the layout without overwriting files.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-datasets.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate_datasets.py
.venv/bin/python scripts/verify_dataset_results.py
```

The pipeline requires all 600 scenario pairs; it does not silently sample. Outputs include all five models at both horizons and all 42 online traces. No Kubernetes or external API access is required after dependencies and data are present.

## Production-source datasets (local only)

- NASA: obtain July and August 1995 HTTP log archives (`NASA_access_log_Jul95.gz`, `NASA_access_log_Aug95.gz`) from the [NASA-HTTP archive page](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html), placing them in `data/nasa/`. That old page has internally inconsistent duration/request-count descriptions; compute counts from actual logs. Record missing intervals separately from zero traffic.
- Alibaba: use the [2018 trace documentation](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018), obtain `container_usage.csv` through its download instructions/survey, and place it in `data/alibaba/`. A documented time/container subset is acceptable. The original paper’s exact release, subset, aggregation and split must be established before claiming reproduction of its MAPE.

Neither production dataset is in the supplied Kaggle archive and neither raw
source is committed. They were evaluated by the separate
`scripts/real_world_forecasting.py` pipeline after legitimate local acquisition;
the committed series, predictions, metrics, preprocessing metadata, source
hashes, and reproduction instructions are under
`results/real_world_forecasting/`. Do not substitute synthetic errors for
production errors or equate this independent protocol with the paper's MAPE.

```bash
.venv/bin/python scripts/real_world_forecasting.py
.venv/bin/python scripts/verify_real_world_forecasting.py
```

## Independent Kaggle source verification

After the initial experiments on the user-supplied ZIP, both datasets were independently downloaded from Kaggle's public download API into `data/source_verification/`. All 1,201 D1 files (1,200 CSVs) and all 87 D2 files (49 CSVs) are byte-identical to the supplied files. This verifies the experimental inputs against the downloaded releases; it does not establish that our forecasting protocol matches the paper.

```bash
curl -fL https://www.kaggle.com/api/v1/datasets/download/cnbrkdmn/phpa-research-datasets -o data/source_verification/phpa-kaggle.zip
curl -fL https://www.kaggle.com/api/v1/datasets/download/cnbrkdmn/workloads-predictional-scaling-patterns -o data/source_verification/online-kaggle.zip
python3 scripts/verify_kaggle_sources.py
```

Create `data/source_verification/` first if needed. Downloaded archives remain local. The committed `results/dataset_phase/kaggle_source_verification.json` records the verification timestamp, source URLs, archive hashes, and every member's downloaded/local hash. A future release may differ; the verifier fails rather than silently accepting changed inputs.
