# Handoff — Dataset & Pattern Evaluation Phase

Give this file to the next agent together with the two Kaggle datasets (or point it at `data/` if they are already there).

**First message to that agent (suggested):**

> Read `HANDOFF_Dataset_Phase.md` and the current docs (`docs/reproduction_report.md`, `docs/methodology.md`, `results/results.md`, `README.md`). Then extend this research using the datasets. Prefer real computed results; do not invent numbers. Keep GitHub in sync when the work is solid. If something blocks you, find another legitimate path and keep going.

---

## 1. Who we are and what this project is

| | |
|---|---|
| Students | Muhammad Usman Al Haq (23i-0585), Muhammad Umar (23i-0782) |
| Course | FAST-NUCES Cloud Computing — 100-day research |
| Repo | https://github.com/umaritics/calibrated-autoscaling-benchmark |
| Local clean tree | `U:\University\Semester 7\Cloud\Research\_repo_clean` (or wherever the user clones the repo) |
| Base paper | Duman & Eken, *From Reactive to Predictive…*, JSS 2026, https://doi.org/10.1016/j.jss.2026.112861 |

**Research question (keep this as the north star):**  
Under which workload patterns does a lightweight predictive scaler (Holt–Winters / similar) beat a *soft* reactive HPA, and how much of that advantage shrinks or reverses when the reactive baseline is **conservatively tuned** (higher CPU target, longer scale-down window)?

We already finished Task 2’s core: live Kubernetes runs on **seasonal** and **burst** (strawman 50% HPA vs Holt–Winters vs tuned 70% HPA), reports, and honest cost/capacity metrics (pod-seconds, hot fraction). That work is on GitHub. Do **not** throw it away — extend it.

---

## 2. End result we want (success looks like this)

When you are done, the repo and docs should make a grader / mentor clearly see:

1. **All paper-relevant datasets are either used or honestly documented** (with sources, sizes, what was run).
2. **Offline evaluation** on the authors’ public synthetic CSVs — real MAPE/RMSE (or equivalent) for at least a lightweight forecaster (Holt–Winters / moving average) and preferably one stronger baseline they used (e.g. a tree model if feasible), broken down **by pattern**.
3. **Pattern coverage** — not only seasonal and burst. Evaluate every pattern that strengthens the RQ: at minimum **seasonal, growing, burst, on/off, chaotic, stepped** where data exists. Prefer live cluster runs for patterns that matter for “when is reactive enough”; use offline forecast accuracy where live runs are too expensive, and say which is which.
4. **Comparison to the paper** — where they publish numbers (e.g. Kaggle early-detection, abstract MAPE / +37.4% / 96.7%), put Original | Ours | Difference (or NOT MEASURED with a real reason). No fake matches.
5. **Our contribution stays visible** — soft HPA vs tuned HPA vs predictive, per pattern, with mean ± SD over repeats when you run live experiments. Do not redefine the gap as a metric that cancels the predictor (see methodology).
6. **GitHub updated** — clean commits, README/docs/results refreshed, no `.venv` or huge raw dumps committed if avoidable (document how to fetch data instead; large zips can stay local or use Git LFS only if necessary).
7. **Write-ups updated** — reproduction report dataset section, methodology, and results tables reflect the new work.

Anything else you find that is **legitimate and useful** for this RQ (e.g. cold-start effects, season-length mismatch, variance across seeds, early-detection recomputed on longer windows) — include it. You are not limited to a fixed checklist of metrics.

---

## 3. Dataset links (download / provide)

### Already expected from the user (2 Kaggle sets)

The user will send these or place them under `data/`:

| Dataset | Link | Role |
|---|---|---|
| PHPA Research Datasets (offline synthetic train/test) | https://www.kaggle.com/datasets/cnbrkdmn/phpa-research-datasets | Offline forecast accuracy by pattern |
| Workloads Predictional Scaling Patterns (online 42 scenarios) | https://www.kaggle.com/datasets/cnbrkdmn/workloads-predictional-scaling-patterns | Authors’ online CSVs / early-detection reference |

If folders are missing, ask the user once for the path or zip. Typical local layout:

```
data/
  phpa/                          # or phpa-research-datasets/
  workloads-predictional-scaling-patterns/
```

### Guide the user to provide these next (do not invent their contents)

| Dataset | Where to get it | Role |
|---|---|---|
| NASA-HTTP | https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html | Paper’s real-world MAPE / generalisation |
| Alibaba Cluster Trace | https://github.com/alibaba/clusterdata (e.g. cluster-trace-v2018 / v2017) | Paper’s real-world MAPE / generalisation |

When guiding the user: tell them **exact page**, **which file(s) to download**, **where to put them** (e.g. `data/nasa/`, `data/alibaba/`), and that full traces are large so a documented subset is fine if they state how it was chosen. If they cannot download something, continue with Kaggle + live patterns and record the gap — do not stop the whole phase.

### Upstream code (for live pattern runs)

- Online harness: https://github.com/syswe/workloads-predictional-scaling-operators  
- Offline / LLM repo (optional): https://github.com/syswe/llm-phpa  
- Operator we used when `syswe/...` image was missing: `jthomperoo/predictive-horizontal-pod-autoscaler:v0.13.2`  
  Helm chart: https://github.com/jthomperoo/predictive-horizontal-pod-autoscaler/releases  

Our overlays live in this repo under `policies/`, `manifests/`, `scripts/`. Prefer extending those rather than rewriting history.

---

## 4. What work was left for you (compute-heavy)

Previously we **documented** datasets but did **not** fully exploit them. Please do the real compute:

1. **Offline on D1 (Kaggle synthetic CSVs)**  
   - Load train/test files across patterns.  
   - Compute forecasting errors properly (MAPE/RMSE/MAE as appropriate).  
   - Report **per pattern**. Sample widely enough that results are credible (not three cherry-picked files unless you justify a stratified sample and list which files).

2. **Authors’ online Kaggle release (D2)**  
   - Parse their CSVs / early-detection summaries.  
   - Align with our live seasonal/burst findings where possible.  
   - If you re-run live experiments, longer windows and all six patterns are valuable.

3. **Live cluster pattern matrix (high value for our RQ)**  
   - Extend beyond seasonal + burst when the machine allows: growing, on/off, chaotic, stepped.  
   - Controllers of interest: strawman HPA, Holt–Winters (or lightweight predictive), conservatively tuned HPA.  
   - Repeats ≥ 3 when feasible; always report variance.  
   - Keep original manifests available; add, don’t silently overwrite.

4. **NASA / Alibaba (when user provides them)**  
   - Aggregate logs/traces into a load series, run the same forecasting evaluation, compare to paper’s “sub-2% MAPE” claim honestly (same or different preprocessing → say so).

5. **Optional but useful**  
   - Early-detection recomputation on longer runs.  
   - Latency probe if you can add it without breaking the harness (turns cost-only story into cost+QoS).  
   - Fix HW season length vs ~80 s seasonal period if you touch live HW configs — document as a labelled variant.

LLM / Gemini reproduction is **optional**. Only do it if the user provides an API key and it clearly helps the RQ; our gap is baseline calibration and patterns, not chatbot classification.

---

## 5. Principles (not a rigid script)

**Freedom:** Choose tools, libraries, batching, and order of work. Prefer correctness over matching a fixed command list.

**Integrity:** Every number in tables must come from a file, script, or cited paper/Kaggle source. If you did not measure it, write `NOT MEASURED` / `NOT RECOMPUTED` and why. Never fabricate, interpolate fake “paper-like” values, or silently drop failed runs.

**No corner cutting on science:** Do not claim “all patterns” if you only ran two. Do not claim MAPE on NASA if you only ran synthetic CSVs. Prefer a smaller honest table over a large fake one.

**If stuck, adapt — do not freeze:**  
Missing Docker image → use the jthomperoo operator (as we did).  
Cluster flaky → finish offline MAPE and document live failures.  
Out of disk/RAM → stratified sample of CSVs with a written sampling plan.  
One pattern’s live run fails → keep going on others; log the failure.  
User delayed on NASA/Alibaba → complete Kaggle + live patterns first.

**Stay aligned:** If a shiny idea does not help “soft vs tuned reactive vs predictive, by pattern,” deprioritise it.

**Review before push:** Re-read your own tables against the CSVs/scripts. Then update GitHub (`calibrated-autoscaling-benchmark`) with clear commits. Ask the user to confirm before force-pushing history; normal commits/pushes to `main` are expected for this phase.

---

## 6. Current artifacts to read first

- `README.md` — project summary and main finding so far  
- `docs/reproduction_report.md` — paper, environment, dataset inventory, deviations  
- `docs/methodology.md` — gap, tuned HPA, ablation map, cost-only framing  
- `results/results.md` + `results/runs/` — live seasonal/burst CSVs (18 runs)  
- `policies/` — strawman HPA, tuned HPA, Holt–Winters  
- `scripts/` — `run_our_arm.sh`, `analyze_our_results.py`, `setup_from_upstream.sh`  

Treat the cost/capacity finding and honest limitations as established baseline; extend them.

---

## 7. Suggested (non-binding) order of attack

1. Confirm `data/` contents; ask user for anything missing.  
2. Offline MAPE-by-pattern on PHPA Kaggle CSVs → write `results/offline_*.md` (or similar).  
3. Summarise authors’ online Kaggle early-detection vs our live numbers.  
4. Live runs for remaining useful patterns (growing, on/off, chaotic, stepped) if Kubernetes is available; else deepen offline.  
5. When NASA/Alibaba arrive → generalisation tables.  
6. Update docs + README + push.

Skip or reorder freely if another path is more reliable on the user’s machine.

---

## 8. What to tell the user when you need help

Be direct. Examples:

- “Please put the PHPA Kaggle zip under `data/phpa` and reply when done.”  
- “Enable Kubernetes in Docker Desktop (4+ CPUs, 8+ GB RAM) and reply `KUBERNETES READY`.”  
- “Download NASA Jul/Aug dumps from [ITA NASA-HTTP](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html) into `data/nasa/`.”  
- “Clone or download an Alibaba cluster-trace release into `data/alibaba/` (link: https://github.com/alibaba/clusterdata).”  

Do not ask for passwords or API keys unless the user already offered them for a specific optional LLM check.

---

## 9. Done criteria (flexible)

You can stop a major milestone when:

- New **computed** results exist for offline patterns and/or additional live patterns,  
- Docs explain what was and was not run,  
- GitHub reflects the work,  
- Nothing important is fabricated or silently omitted.

If time remains, push further (NASA/Alibaba, latency, longer windows). If not, leave a short `docs/STATUS_DATASET_PHASE.md` with what remains — still useful, still honest.
