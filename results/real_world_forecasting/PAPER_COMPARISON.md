# Comparison with Duman and Eken

The accessible paper abstract states that gradient boosting models achieved sub-2% MAPE on NASA and Alibaba. The authors' public repository is more specific: NASA is described as 3.46 million July–August requests aggregated into 5-minute intervals (16,364 samples), while Alibaba is described as machine utilization from 20 machines (2,240 intervals). It reports NASA CatBoost MAPE 0.40%, NASA GBDT 1.36%, Alibaba GBDT 0.75%, and other model values.

Neither accessible source establishes the exact real-world chronological boundaries, forecast horizon, lag features, zero-target MAPE rule, 20-machine identifiers, or model-selection code needed for an independent numerical reproduction. Our retained Alibaba source is container usage rather than the paper repository's described machine utilization target.

| Dataset | Original model | Original metric/value | Our model | Our metric/value | Protocol comparable? | Explanation |
|---|---|---|---|---|---|---|
| NASA | GBDT | MAPE 1.36% | HistGradientBoostingRegressor | MAPE(nonzero) 41.6072% at 300s | NO — NOT DIRECTLY COMPARABLE | Different target/subset, split, features, horizon and zero handling; no numerical difference is valid. |
| NASA | GBDT | MAPE 1.36% | HistGradientBoostingRegressor | MAPE(nonzero) 65.2408% at 3600s | NO — NOT DIRECTLY COMPARABLE | Different target/subset, split, features, horizon and zero handling; no numerical difference is valid. |
| ALIBABA | GBDT | MAPE 0.75% | HistGradientBoostingRegressor | MAPE(nonzero) 15.2773% at 10s | NO — NOT DIRECTLY COMPARABLE | Different target/subset, split, features, horizon and zero handling; no numerical difference is valid. |
| ALIBABA | GBDT | MAPE 0.75% | HistGradientBoostingRegressor | MAPE(nonzero) 15.2691% at 60s | NO — NOT DIRECTLY COMPARABLE | Different target/subset, split, features, horizon and zero handling; no numerical difference is valid. |

The paper's 37.4% pattern-aware improvement and 96.7% LLM classification accuracy are NOT RECOMPUTED in this milestone. No numerical difference from the real-world paper values is calculated because the protocols are not comparable.

Sources: https://doi.org/10.1016/j.jss.2026.112861 ; https://github.com/syswe/llm-phpa ; https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018
