# What to submit (this deliverable)

1. GitHub link: https://github.com/umaritics/calibrated-autoscaling-benchmark  
2. `docs/reproduction_report.md` (includes full **Datasets** inventory for step 3)  
3. `docs/methodology.md`  
4. `results/results.md` (optional but recommended as evidence)

One-sentence claim for the mentor:

> On a live Kubernetes cluster, Holt–Winters beats a soft 50% HPA on capacity (pod-seconds), but a conservatively tuned 70% HPA uses even less capacity than Holt–Winters on seasonal traffic; this is a cost finding only (no latency measured), and the paper’s LLM / MAPE numbers were not re-run.
