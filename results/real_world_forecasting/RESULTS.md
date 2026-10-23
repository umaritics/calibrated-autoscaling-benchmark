# Genuine real-world forecasting evaluation

These are rolling-origin held-out forecasts on raw NASA requests and native-timestamp Alibaba CPU observations. Forecast accuracy is supporting evidence only; it is not a Kubernetes cost, latency, or controller comparison.

## Held-out metrics

| dataset | horizon_seconds | model | pairs | mae | rmse | mape_nonzero | wape | smape | mape_undefined_zero_pairs |
|---|---|---|---|---|---|---|---|---|---|
| nasa | 300 | persistence | 1588 | 41.6096 | 54.8096 | 32.1783 | 21.2099 | 24.8467 | 1 |
| nasa | 300 | moving_average | 1588 | 39.1351 | 52.0513 | 49.7797 | 19.9486 | 22.9533 | 1 |
| nasa | 300 | exponential_smoothing | 1588 | 38.4314 | 50.5095 | 44.1307 | 19.5899 | 22.7108 | 1 |
| nasa | 300 | gbdt | 1588 | 36.3206 | 47.8176 | 41.6072 | 18.5139 | 21.3181 | 1 |
| nasa | 3600 | persistence | 1577 | 57.0051 | 75.2437 | 67.2705 | 28.9882 | 33.1282 | 1 |
| nasa | 3600 | moving_average | 1577 | 53.2895 | 70.8402 | 63.2161 | 27.0988 | 30.2846 | 1 |
| nasa | 3600 | exponential_smoothing | 1577 | 51.1395 | 66.9358 | 63.9335 | 26.0054 | 30.4200 | 1 |
| nasa | 3600 | gbdt | 1577 | 50.8335 | 66.6083 | 65.2408 | 25.8498 | 29.0264 | 1 |
| alibaba | 10 | persistence | 698 | 2.3945 | 2.9887 | 21.0341 | 20.1184 | 20.2639 | 0 |
| alibaba | 10 | moving_average | 698 | 1.8536 | 2.2983 | 16.4789 | 15.5737 | 15.7103 | 0 |
| alibaba | 10 | exponential_smoothing | 698 | 1.8246 | 2.2553 | 16.3493 | 15.3301 | 15.4606 | 0 |
| alibaba | 10 | gbdt | 698 | 1.7249 | 2.1295 | 15.2773 | 14.4921 | 14.6556 | 0 |
| alibaba | 60 | persistence | 693 | 2.3459 | 2.9260 | 20.6434 | 19.7242 | 20.0043 | 0 |
| alibaba | 60 | moving_average | 693 | 1.8225 | 2.2585 | 16.1650 | 15.3235 | 15.4613 | 0 |
| alibaba | 60 | exponential_smoothing | 693 | 1.7852 | 2.2048 | 16.1249 | 15.0101 | 15.1240 | 0 |
| alibaba | 60 | gbdt | 693 | 1.7271 | 2.1328 | 15.2691 | 14.5218 | 14.6765 | 0 |

MAPE is computed only where the actual target is nonzero; the final column exposes every undefined zero-target pair. MAE, RMSE, WAPE, and sMAPE use all pairs. WAPE is 100 × total absolute error / total absolute actual. sMAPE is the mean of 200 × absolute error / (|actual| + |prediction|), with a zero term when both are zero.

## Lowest held-out MAE

| dataset | horizon_seconds | model | mae |
|---|---|---|---|
| alibaba | 10 | gbdt | 1.7249 |
| alibaba | 60 | gbdt | 1.7271 |
| nasa | 300 | gbdt | 36.3206 |
| nasa | 3600 | gbdt | 50.8335 |

## Paired model interpretation

| dataset | horizon_seconds | ES vs persistence MAE reduction | ES vs moving-average MAE reduction | GBDT vs ES MAE reduction |
|---|---|---|---|---|
| alibaba | 10 | 23.80% | 1.56% | 5.47% |
| alibaba | 60 | 23.90% | 2.05% | 3.25% |
| nasa | 300 | 7.64% | 1.80% | 5.49% |
| nasa | 3600 | 10.29% | 4.03% | 0.60% |

Exponential smoothing improves MAE over both persistence and the moving average at every compatible horizon. GBDT has the lowest MAE in all four comparisons, but its incremental gain over exponential smoothing is only 0.60% for NASA at 60 minutes and 3.25% for Alibaba at 60 seconds. The simple smoother is therefore close to the more complex model in those cases. NASA errors increase markedly from 5 to 60 minutes; Alibaba errors are similar at 10 and 60 seconds for this aggregated window. There are no repeated folds or independently sampled Alibaba container groups, so no variance or significance claim is made.

## Dataset construction

NASA: 1,891,714 requests parsed, 1 unparsed final fragment, 7,938 complete 5-minute bins, and 6 zero-request bins. The trailing partial bin is excluded.

Alibaba: 2,308,039 complete rows decoded from the bounded prefix. The deterministic aggregate uses 2,429 completed named container blocks and selects 3,489 consecutive native 10-second timestamps with at least 20 contributors each. The final truncated identifier is excluded; no gap is filled.

## Interpretation limits

NASA is request-count demand; Alibaba is observed-container mean CPU percent. Their errors and percentage metrics must not be pooled or compared as if they share a target. The Alibaba prefix is nonrandom and its cross-container membership varies by timestamp. The retained NASA evaluation uses July only and includes calendar zeros; the paper repository describes July–August nonempty-bin aggregation. These protocols therefore answer an independent reproducible question, not a numerical reproduction of the paper.

Protocol and exact boundaries are in `evaluation_protocol.json`; every test prediction is in `predictions.csv`.
