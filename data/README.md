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

## Not supplied

- NASA: obtain July and August 1995 HTTP log archives (`NASA_access_log_Jul95.gz`, `NASA_access_log_Aug95.gz`) from the [NASA-HTTP archive page](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html), placing them in `data/nasa/`. That old page has internally inconsistent duration/request-count descriptions; compute counts from actual logs. Record missing intervals separately from zero traffic.
- Alibaba: use the [2018 trace documentation](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018), obtain `container_usage.csv` through its download instructions/survey, and place it in `data/alibaba/`. A documented time/container subset is acceptable. The original paper’s exact release, subset, aggregation and split must be established before claiming reproduction of its MAPE.

Neither production dataset is in the supplied archive or evaluated by this pipeline. Do not substitute synthetic errors for production errors.
