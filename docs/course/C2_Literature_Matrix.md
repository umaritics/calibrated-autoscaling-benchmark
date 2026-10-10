# Cutoff 2 — Literature & Research Gap Matrix
### Project: Calibration-Gap Autoscaling Benchmark (Grp 23i-0585 / 23i-0782)

**Instructions (per guide Cutoff 2, Oct 3):** synthesize ~15–20 relevant papers *thematically* (not one-by-one summaries). Compare methods, datasets, metrics, findings, and limitations, then justify the defensible gap. This file is **seeded with 12 verified papers**; expand to 15–20 (targets flagged below). Owner: Muhammad Umar (with Usman on systems/metrics columns).

> Verification rule: before adding any paper, open the DOI/arXiv link and confirm authors + venue. Fabricated or mis-cited references are a zero-tolerance item (guide Sections 25–26).

---

## Thematic buckets to cover
1. Reactive / threshold autoscaling & HPA tuning (baseline behaviour, cooldown/stabilization).
2. Lightweight forecasting autoscalers (Holt-Winters, moving average, ARIMA, KEDA-based).
3. Regime / pattern / burst-aware autoscaling.
4. RL-based autoscaling & the calibrated-baseline critique.
5. Workload characterization of cloud traces (burstiness, periodicity).
6. Autoscaling benchmarks & reproducibility.

---

## Matrix (seed set — all verified)

| # | Paper (year, venue) | Problem | Method | Dataset / Setup | Metrics | Key finding | Limitation → our gap |
|---|---|---|---|---|---|---|---|
| 1 | Cortez et al., **Resource Central**, SOSP 2017 | Predict VM workloads for resource mgmt | ML workload prediction in production | Azure production traces (→ Azure Public Dataset) | Prediction accuracy, utilization | Workload prediction is feasible at scale; source of Azure trace | Provider-side, not a reactive-vs-predictive autoscaling comparison |
| 2 | Microsoft, **AzurePublicDataset** (2019–24) | Public cloud trace release | Dataset/artifact | VM + Functions traces | — | Public traces enabling reproducible study | Dataset only; no policy evaluation |
| 3 | Abdullah et al., **Burst-Aware Predictive Autoscaling**, IEEE TSC 2022 | Bursty microservice scaling | Burst-aware predictive scaler | Containerized microservices | SLA, cost | Burst awareness improves scaling | Proposes a system; HPA baseline not calibration-analyzed |
| 4 | Kumar, Verma, Buyya, **Predictive Autoscaling Taxonomy & Future Directions**, arXiv 2606.07046 (2026) | Survey/taxonomy | Taxonomy; MAPE; drift/uncertainty | Cloud-native + edge | — | Names drift-aware, autonomous, reproducible as open | Survey; no empirical calibration-gap study |
| 5 | Liu et al., **BACC**, arXiv 2606.20575 (2026) | Budget-aware horizontal autoscaling | Conformal calibration + PI control wrapping a forecaster | Azure Functions traces + K8s replay | Compliance gap, violations | Online calibration tightens budget compliance vs HPA | Focus on budget calibration, not per-regime reactive-vs-predictive |
| 6 | **PAHPA**, IEEE TSC 2026 (10.1109/TSC.2026.3685325) | Prediction-assisted HPA | LightGBM + queueing + correction | K8s | Violation rate, p99 latency | Prediction + real-time monitoring beats HPA | New system vs (likely default) HPA; not a calibration-gap benchmark |
| 7 | Machiraju, Kumar, Sharma, **ML-Based Autoscaling Survey**, Math. Comput. Appl. 31(2):49 (2026) | Survey of 60 studies (2015–25) | 5-dim taxonomy | — | — | Field fragmented; reproducibility poor; cost–SLO–energy under-studied | Directly motivates reproducible, standardized benchmark |
| 8 | Schröder, Böhm, Lampe, **Comparison of Autoscaling Frameworks**, arXiv 2311.18659 (2023) | Compare autoscaling frameworks | Empirical comparison local vs cloud | Containerized ML apps | Scaling behaviour | Framework choice matters | Not regime-stratified; not calibration-gap focused |
| 9 | Zhang, Sun, Zhao, Chu, Sarkani, Fossaceca, **RLScale-Bench ("When Does Deep RL Beat Calibrated Baselines?")**, arXiv 2605.26418 (2026) | Is RL better than tuned rule-based? | 6 RL algos vs calibrated HPA; matched budgets | K8s HPA; 6 workloads × 5 seeds (240 runs) | Cost, constraint violations | **Calibrated rule-based wins on cost on all 6; no algo dominates; calibration is the bottleneck** | RL-vs-HPA only; **not lightweight forecasters; not regime-stratified** ← our niche |
| 10 | Baghel, **ADAPT**, arXiv 2605.15788 (2026) | Cold-start-aware proactive scaling | EWMA cold-start est. → MPC horizon | Simulator; 6 archetypes × 5 seeds; Wilcoxon | SLA violation % | MPC+LSTM <5% SLA viol. vs 7–19% HPA | Simulator-only; deep MPC; not a calibrated-baseline gap study |
| 11 | Jeong & Jeong, **ARAScaler**, IEEE TSC 18(1):72–84 (2025) | Adaptive container scaling | ETimeMixer (deep) + burst/nonburst/dynamic/static states | Offline sim, 7 traces | Utilization, overload, #updates | State-segmented scaling improves efficiency | Deep model; HPA treated as inferior; no reproducible harness |
| 12 | Duman & Eken, **From Reactive to Predictive (PHPA)**, J. Systems & Software (2026). **Reproduction target (Task 2).** | Pattern-aware predictive HPA | 6-pattern taxonomy + per-pattern model selection + LLM classifier; online harness also runs Holt–Winters, Linear, GBDT, CatBoost, VAR, XGBoost vs HPA | 600 offline scenarios; online 6 patterns × 7 strategies. Code: `syswe/workloads-predictional-scaling-operators`, `syswe/llm-phpa`, Kaggle | Forecast MAE, classification accuracy; online early-detection time and replica/CPU traces | Pattern-specific model selection: +37.4% forecast accuracy; Gemini classifier 96.7% | Online HPA is **target CPU 50%, max 20 replicas** — a default, not a calibrated baseline. Headline claims are forecast/classification accuracy. Patterns are synthetic, not Azure traces. Gap we add: calibration gap + regime switch. Do not describe this paper as “forecast only.” |

---

## Papers still to add (target 15–20) — suggested searches
- [ ] **BAScaler / BASE** (IEEE TSC 2026, 10.1109/TSC.2026.3668105) — burst-adaptive stacked ensembles (bucket 3).
- [ ] A **KEDA / event-driven autoscaling** empirical paper (bucket 2).
- [ ] A **Kubernetes HPA cooldown/stabilization tuning** study (bucket 1) — needed to justify "realistic" baseline settings.
- [ ] A **workload burstiness/periodicity characterization** paper for cloud traces (bucket 5) — grounds the regime features (CoV, ACF, FFT).
- [ ] 1–2 more **RL / DRL autoscaling** papers that RLScale-Bench critiques (bucket 4), to show the calibrated-baseline debate.
- [ ] A **reproducibility / benchmarking methodology** paper in systems (bucket 6) — supports the CI-reproducible contribution.

---

## Synthesis skeleton (write these paragraphs for C2)
1. **Reactive baselines & why calibration matters** (buckets 1, 4) — lead with RLScale-Bench: tuned baselines change conclusions.
2. **Predictive & pattern/regime-aware autoscaling** (buckets 2, 3) — ARAScaler, PHPA, ADAPT, Abdullah: strong methods, but per-regime *policy* comparison + fair baseline is missing.
3. **Reproducibility crisis** (bucket 6 + survey [7]) — fragmented evaluation motivates a CI-reproducible benchmark.
4. **Gap statement** — restate the residual gap: lightweight predictive vs calibrated HPA, per burst regime, with an explicit calibration-gap metric, fully reproducible on kind/CI.
