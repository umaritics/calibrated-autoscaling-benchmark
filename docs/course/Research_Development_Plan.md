# Research Development Plan
### When Does a Calibrated Reactive Baseline Beat a Predictive Autoscaler? A Reproducible, Regime-Stratified Benchmark on Real Cloud Traces
**Cloud Computing — 100-Day Research Assignment (2026)**

| | |
|---|---|
| **Group** | G## (from Google Sheet) — Section A |
| **Primary Researcher** | Muhammad Usman Al Haq (23i-0585) |
| **Co-Researcher** | Muhammad Umar (23i-0782) |
| **Approved Direction** | AI-Driven Cloud Resource Optimization (∩ Autonomous / Self-Adaptive Cloud) |
| **Target venue** | Journal, Impact Factor ≥ 1.0 (Journal of Cloud Computing / Cluster Computing / IEEE Access / SoftwareX) |
| **Project window** | Aug 30 → Dec 7, 2026 (100 days) |
| **Repo** | `calibrated-autoscaling-benchmark` |

---

## 1. One-Paragraph Summary

A large body of work claims ML-based predictive autoscaling beats reactive Kubernetes HPA — but recent 2026 evidence (RLScale-Bench) shows the decisive factor is often **baseline calibration**, not the algorithm, and that **reproducible, regime-stratified** evaluation is largely missing. This study is a **benchmark**, not a new system. On real Azure public traces we (1) classify workload segments into interpretable burst regimes, (2) compare a **realistically calibrated HPA** against a **lightweight, non-deep-learning predictive scaler** (KEDA + Holt-Winters) **per regime**, and (3) quantify the **calibration gap** — how much predictive's apparent advantage vanishes once the reactive baseline is properly tuned. Everything runs free on `kind` + GitHub Actions; the offline characterization (Phase 1) is a guaranteed standalone result.

**Core hypotheses (falsifiable)**
- **H1** — the predictive-vs-reactive gap shrinks or reverses when HPA is properly calibrated, especially on chaotic/spike regimes.
- **H2** — predictive advantage is largest on periodic/gradual regimes, smallest on chaotic/spike regimes.
- **H3** — the calibration gap (advantage under strawman HPA − advantage under calibrated HPA) is statistically significant and regime-dependent.
- **Null-result guard** — if a calibrated HPA matches predictive on most regimes, that is itself a valid, publishable finding (see §10.1).

### 1.1 Task 2 alignment (locked 5 Oct 2026)

Task 2 is the graded workflow for this same project: reproduce one existing study, write the reproduction report, agree a gap with the mentor, then add an improvement and ablate it. Building a new benchmark from an empty repository does not satisfy that rubric. RLScale-Bench stays the motivation. It is not the paper we reproduce: 240 deep-RL runs are not feasible on a laptop, and the study we can actually re-run already contains the Holt–Winters versus HPA comparison our question needs.

**Reproduction target (do not switch without the mentor):** Duman & Eken, “From Reactive to Predictive,” *Journal of Systems and Software*, 2026. DOI [10.1016/j.jss.2026.112861](https://doi.org/10.1016/j.jss.2026.112861).

| Piece | Where |
|---|---|
| Online experiment harness (42 scenarios: 6 patterns × 7 strategies) | [syswe/workloads-predictional-scaling-operators](https://github.com/syswe/workloads-predictional-scaling-operators) |
| PHPA operator image / source | [syswe/predictive-horizontal-pod-autoscaler](https://github.com/syswe/predictive-horizontal-pod-autoscaler) |
| Offline models, pattern code, Kaggle-linked datasets | [syswe/llm-phpa](https://github.com/syswe/llm-phpa) |

Their published reactive baseline is a default HPA: `targetCPUUtilization: 50%`, `maxReplicas: 20`. That is our **strawman** arm, not the calibrated one. Holt–Winters in that harness (`α=0.9`, `β=0.2`, `γ=0.3`, season length 6, 20 s lookahead) is the lightweight predictor. The six patterns (seasonal, growing, burst, on/off, chaotic, stepped) are the regime axis.

**Improvement, only after a reproduction table exists and the mentor agrees:**

- Keep their default HPA and their Holt–Winters manifests unchanged, so the original system remains the baseline.
- **Component A — calibration.** A second HPA with a documented target and stabilization / scale-down window. The calibration gap is predictive-advantage(strawman) minus predictive-advantage(calibrated), per pattern.
- **Component B — regime switch.** Use Holt–Winters only on forecastable patterns (seasonal, growing). Use the calibrated HPA on burst and chaotic patterns, where a forecast has little to lock onto.
- Ablation required by Task 2: original harness; original + A; original + B; original + A + B.
- Azure public-trace segments are the **second dataset** (generalization). They are not the first experiment.

**This week (5–12 Oct), before any new scaler code:** Docker Desktop Kubernetes (or `kind`), `make bootstrap`, then one pattern only — seasonal, default HPA versus Holt–Winters (`make quick-test` or a single pattern from `make patterns`). Record paper value, our value, and the difference. A metric that needs a paid LLM API (their Gemini pattern classifier, reported at 96.7%) is documented as not reproduced. Do not run all 42 scenarios on day one.

---

## 2. Research Question & Objectives

**Primary RQ.** Under which workload burst regimes, on real Azure public-trace data, does a lightweight predictive autoscaler (KEDA + Holt-Winters/moving-average) outperform a realistically calibrated Kubernetes HPA — and how much of the advantage reported in prior work disappears when the reactive baseline is properly tuned?

| Obj | Description | Owner | Cutoff |
|---|---|---|---|
| **O1 Characterize** | Segment + classify Azure traces into interpretable burst regimes (rule-based primary) | Umar | C2→C3 |
| **O2 Calibrate** | Tuned HPA (realistic thresholds/cooldown) + lightweight predictive KEDA scaler | Usman | C3 |
| **O3 Benchmark per regime** | Per-regime "regime → policy" performance matrix on live kind cluster | Both | C3 |
| **O4 Quantify calibration gap** | Re-run vs strawman HPA; measure how much advantage is baseline artifact | Both | C3→C4 |

---

## 3. Positioning vs Closest 2025–2026 Work (all verified real)

| Paper | What it does | What it does NOT do (our room) |
|---|---|---|
| **ARAScaler** (IEEE TSC 2025) | Deep (ETimeMixer) scaler; segments burst/nonburst/dynamic/static | No fair-tuned-HPA comparison; no reproducible harness |
| **PHPA / Duman & Eken** (JSS 2026) — **reproduction target** | 6 patterns; Holt–Winters and five other models vs default HPA; public harness | HPA is target-CPU 50% only; no calibrated arm; headline numbers are forecast/classification accuracy; synthetic patterns, not Azure traces |
| **RLScale-Bench** (arXiv 2026) | Calibrated HPA vs 6 RL algos, 6 workloads × 5 seeds | RL-vs-HPA only; **not** lightweight forecasters; not regime-stratified |
| **ADAPT** (arXiv 2026) | MPC+LSTM/Prophet vs HPA, 6 archetypes, simulator | Deep MPC, simulator-only; cold-start horizon focus, not calibration gap |

**Our defensible niche:** lightweight (non-deep-learning) predictive **vs a fairly-calibrated HPA**, **stratified by burst regime**, with an explicit **calibration-gap** measurement and **full CI reproducibility** on `kind`.

---

## 4. Milestone Map (graded cutoffs)

| Cutoff | Day | Date | Deliverable | Marks |
|---|---|---|---|---|
| **C1 Proposal** | 10 | Sep 8 | Proposal, setup, Sheet | 15 |
| **C2 Literature & Gap** | 35 | Oct 3 | 15–20 papers synthesized, defensible gap, refined RQ | 20 |
| **C3 Method & Prelim Results** | 65 | Nov 2 | Full method, working benchmark, preliminary per-regime results | 25 |
| **Day-80 Draft** | 80 | Nov 17 | Complete draft (ungraded, feedback) | — |
| **Final + Defense** | 100 | Dec 7 | Manuscript, poster, GitHub, submission evidence, defense | 40 |

> Missing a cutoff = **0** for it. Accepted paper → `max(marks,100)`; Rejected → `min(marks,10)`.

---

## 5. Phase-by-Phase Plan

### Phase 0 — Cutoff 1 (close out now)
- [ ] Submit proposal (`_FINAL.docx`); paste `.tex` into Overleaf template.
- [ ] Google Sheet complete (IDs/emails, area, title, RQ, keywords, status C1, venue class).
- [ ] Overleaf renamed `[Grp#_23i0585_23i0782_calibrated_autoscaling_benchmark]`; Umar + instructor added as Editors.
- [ ] Public repo `calibrated-autoscaling-benchmark` (README, LICENSE, `.gitignore`, stub `ci.yml`).
- [ ] Notify instructor the topic is finalized as the calibration-gap benchmark.

### Phase 1 — Days 11–35 → **C2: Literature & Gap** (Oct 3)
- **Umar (lead):** complete the literature matrix in `C2_Literature_Matrix.md` (seeded with 12 verified papers), expand to 15–20. Themes: reactive/HPA tuning; lightweight forecasting autoscalers; regime/pattern-aware autoscaling; RL autoscaling & calibrated-baseline critiques; workload characterization; autoscaling benchmarks/reproducibility.
- **Usman (support):** build the skeleton harness (kind boot, sample service, HPA deploy, Locust smoke test, Prometheus scrape) in `make demo` + `ci.yml` so C3 isn't a cliff.
- **Both:** write C2 sections in Overleaf (Related Work, refined gap, refined RQ/objectives).
- **Exit:** matrix complete; gap justified by cited limitations; harness boots in CI.

### Phase 2 — Days 36–65 → **C3: Method & Preliminary Results** (Nov 2)

Do these in order. Step 0 is the Task 2 reproduction report. Steps 3–5 are the improvement and are blocked on mentor agreement.

0. **Reproduce PHPA (Usman leads, Umar runs a second seed).** Clone `workloads-predictional-scaling-operators`. Bootstrap Docker Desktop Kubernetes or `kind`. First run: seasonal pattern, default HPA vs Holt–Winters. Second run: burst or chaotic. Fill the Task 2 table (metric / paper / reproduced / difference) for early-detection time, replica trace, and any forecast MAE the offline `make offline` path prints. Write `docs/reproduction_report.md` from the Task 2 template (hardware, library versions, deviations, what failed). Gemini classification is out of scope.
1. **O1 Characterization pipeline (Umar), in parallel with step 0.** Rule-based regime labels on Azure trace windows (primary, fixed a-priori thresholds); k-means only for exploratory validation with fixed seed + stability check. Map their six pattern names onto our four regimes so the two datasets are comparable. *(Standalone result if the cluster slips.)*
2. **Mentor checkpoint (Both), before new policy code.** Send the reproduction table, the failure log, and the proposed A/B improvement in §1.1. Do not start Component A or B until the direction is agreed.
3. **O2 Policies (Usman).** Add manifests beside theirs, do not replace them. (i) **Calibrated HPA** — documented target + stabilization/cooldown. (ii) **Regime switch** — Holt–Winters on seasonal/growing, calibrated HPA on burst/chaotic. Their 50% HPA and their Holt–Winters YAML stay as the original baseline.
4. **O3 Per-regime benchmark (Both).** Ablation matrix: original; +A; +B; +A+B, on at least seasonal and burst, N≥3. *(C3 headline.)*
5. **O4 Calibration-gap + second dataset (Both).** Gap = advantage(strawman HPA) − advantage(calibrated HPA) per pattern. If step 0 is stable, replay one Azure-derived demand segment through the same harness.
6. **Automation + experiment budget (Usman).** **CI is not the experiment runner** — GitHub Actions free tier (~2,000 min/mo) can't absorb the full matrix. Run the matrix **locally**; CI runs only a **smoke test**. Do not schedule all 42 PHPA scenarios × 3 seeds. C3 budget: **2 patterns × 4 ablation arms × 3 seeds**.

**Exit:** methodology documented; benchmark runs end-to-end; ≥1 real per-regime comparison + preliminary calibration-gap numbers; troubleshooting log kept.

### Phase 3 — Days 66–85 → **Day-80 Complete Draft** (Nov 17)
- **Both — experiments:** full matrix, all regimes; calibration-gap magnitudes; ablations (horizon, HPA cooldown, window size); N≥3 repeats + Cohen's d / significance.
- **Usman — analysis/figures:** per-regime tables, A-vs-B gap plots, trade-off (SLA vs over-provisioning) plots.
- **Umar — writing:** Abstract → Conclusion in Overleaf. **Abstract's last line = GitHub link** (mandatory).
- Submit complete draft Day 80 for instructor feedback.

### Phase 4 — Days 86–100 → **Final + Defense** (Dec 7)
- Revise per feedback; freeze results; finalize reproducibility (fork → CI reproduces smoke result).
- One-page **poster PDF** (problem, gap, RQ, architecture, setup, key results, conclusion, GitHub QR, course ID).
- **Instructor review before submission** (required). Select journal (IF ≥ 1.0), format, **submit**, retain evidence.
- Rehearse **defense** — either student can explain any part.

---

## 6. Technical Architecture & Repo Layout

**Stack (all free):** `kind` · Kubernetes HPA · KEDA external scaler · Prometheus · Locust · GitHub Actions · Python (pandas, scikit-learn, statsmodels).
**Excluded:** RAPL/Kepler energy metering (unreliable in virtualized/kind — see risk register).

```
calibrated-autoscaling-benchmark/
├── README.md                # overview + one-command reproduction
├── LICENSE                  # MIT/Apache-2.0
├── .gitignore               # Python + K8s
├── requirements.txt
├── data/README.md           # how to fetch Azure Public Dataset (no raw data committed)
├── characterization/        # O1 — offline (guaranteed deliverable)
│   ├── features.py          # CoV, ACF, FFT spectral entropy, amplitude, trend
│   ├── classify.py          # rule-based (primary) + k-means (validation, fixed seed)
│   └── notebooks/
├── workload/
│   ├── service/             # simple CPU-bound HTTP service + Dockerfile
│   └── locust/              # per-regime request schedules
├── policies/
│   ├── hpa_calibrated/      # tuned HPA manifests
│   ├── hpa_strawman/        # un-tuned HPA (for calibration-gap condition B)
│   └── predictive_keda/     # KEDA external scaler (Holt-Winters/moving average)
├── experiments/
│   ├── run_experiment.py    # cluster up → deploy → load → collect → teardown
│   ├── conditions.py        # A / B / C calibration-gap conditions
│   ├── metrics/             # Prometheus queries
│   └── results/             # committed CSVs + figures (regeneration scripts)
├── analysis/
│   ├── make_figures.py      # per-regime matrix, A-vs-B gap plots
│   └── stats.py             # repeats, Cohen's d, significance
├── .github/workflows/ci.yml # smoke test + one-scenario reproducibility check
└── docs/troubleshooting.md  # corrective-action log (C3 requirement)
```

**Reproducibility contract:** fork → CI smoke test reproduces one scenario; full matrix reproducible locally via `make experiment`.

---

## 7. Evaluation Metrics

| Category | Metrics |
|---|---|
| SLA / QoS | SLA violation rate; p95 & p99 latency; error rate |
| Efficiency | Over-provisioning ratio; wasted pod-hours |
| Stability | # scaling events; thrashing frequency |
| **Regime** | **Per-regime breakdown of all above** (central evidence) |
| **Calibration gap** | advantage(strawman HPA) − advantage(calibrated HPA), per regime |
| Model | Forecast MAE/RMSE per regime |

Rigor: **N ≥ 3** repeats/cell (matrix sized to budget, §5 Phase 2 step 6); mean ± std; **Cohen's d**; significance tests; report **magnitude** not just winner; no cherry-picking; report regimes where HPA ties/wins.

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Saturation / weak novelty** | High | High | Reframed as **benchmark + calibration-gap** (validated by RLScale-Bench); lightweight-vs-tuned-HPA + regime stratification + reproducibility is the open niche |
| Live-cluster flakiness near deadline | High | High | Reproduce one PHPA pattern first; **fallback = their `make offline` forecast metrics** plus the Azure characterization (same RQ, no cluster) |
| Task 2 graded as reproduce-then-improve, while the repo is still an empty benchmark sketch | High | High | §1.1: PHPA harness is the baseline; our repo records the reproduction and the added A/B arms |
| k-means labels unstable across runs | Med | High | **Rule-based labels primary/fixed-a-priori**; k-means exploratory only, fixed seed + stability check |
| CI/compute budget exceeded (~2000 min/mo) | High | Med | Full matrix **local**; CI = smoke + one-scenario reproducibility check; matrix 4×3×3 |
| "Result is obvious" critique | Med | High | Report **magnitude** of per-regime delta + **calibration-gap** size; fairly-tuned baseline; null result framed as finding |
| Time contention with FYP | High | Med | Weekly cadence; Umar=lit/characterization, Usman=systems/CI; hard date buffers |
| Journal rejection (min-10 rule) | Med | High | Instructor review first; appropriate IF≥1.0 venue; submit early enough for evidence |
| Fabricated/incorrect citations | Low | Critical | All 12 refs verified to resolve; correct authors/DOIs; CI artifacts back all numbers |

---

## 9. Responsibility Split & Cadence

| Area | Usman (Primary) | Umar (Co) |
|---|---|---|
| Overleaf coordination | **R** | C |
| kind / HPA / KEDA / CI pipeline | **R** | C |
| Literature review & synthesis | C | **R** |
| Characterization pipeline & preprocessing | C | **R** |
| GitHub repo / README / license | C | **R** |
| Results analysis, figures, stats | **R** | **R** |
| Poster, defense prep | **R** | **R** |

- **Weekly:** 30-min sync; commit to GitHub; update Overleaf. Maintain a contribution log (guide Section 27).

| Date | Student | Contribution | Evidence/Link |
|---|---|---|---|
| | | | |

---

## 10. Publication Plan

1. **Candidate venues (IF ≥ 1.0, journals only):** Journal of Cloud Computing (Springer), Cluster Computing (Springer), IEEE Access, SoftwareX (strong fit for the reproducible artifact), Computing (Springer), Journal of Grid Computing.
2. Match manuscript length/format to the chosen venue.
3. **Instructor review before submission** (mandatory).
4. Submit; **retain submission evidence**.
5. If "Under review" at Day 100 → provide evidence; instructor applies course policy.

### 10.1 Null-Result Handling Strategy (decided in advance)
- **If a calibrated HPA matches predictive on most regimes:** report as "predictive infrastructure is not worthwhile for these workload mixes," and quantify *how much* prior advantage was a calibration artifact — a practitioner-relevant negative result.
- **If predictive dominates uniformly:** report the *magnitude* per regime and the calibration-gap size (still novel: nobody measured it with a fair baseline + reproducible harness).
- **Either way**, O1 characterization + O3 per-regime matrix remain complete, publishable results.
- The RQ is framed as an open question, pre-empting the "what if your hypothesis is wrong" attack.

---

## 11. Definition of Done (final checklist)

- [ ] Two students; group/topic final in Google Sheet.
- [ ] RQ clear; literature + gap complete; methodology documented.
- [ ] Results are actual evidence (CI + committed artifacts); analysis with significance.
- [ ] Overleaf manuscript complete; instructor has continuous access.
- [ ] Public GitHub reproducible; **last line of abstract = GitHub link**.
- [ ] One-page poster PDF done.
- [ ] References verified (authors + DOIs); no credentials/private data committed.
- [ ] Instructor reviewed before submission; appropriate venue; submitted with evidence retained.
- [ ] Both students can defend the complete project.
