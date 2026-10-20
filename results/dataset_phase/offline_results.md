# Offline forecast results: all 600 supplied scenarios

All 1,200 CSVs pass finite/nonnegative target, chronological split, and exact 15-minute continuity checks. Each scenario has 2,688 train and 672 test observations: 2,016,000 total, 403,200 held-out targets per model at horizon 1 and 401,400 at horizon 4. No sampling or exclusions.

Rolling-origin evaluation: 1 step = 15 minutes; 4 steps = 60 minutes. Origins begin after the full training window; at horizon 4 the first target is test[3]. Only observations available before the forecast origin are used. Earlier test observations become available as time advances. GBDT is trained once on training labels only. This is not a fixed-origin 672-step forecast, nor a Kubernetes controller simulation.

MAE and RMSE are in pods. Tables macro-average per-scenario errors (100 scenarios per pattern). SD is across scenarios, not repeated experiments. MAPE excludes zero targets explicitly; MAE includes them. WAPE is 100 × total absolute error / total absolute target per scenario.

## Horizon 1 steps

| pattern | model | scenarios | mae | mae_sd | rmse | mape_nonzero | wape |
|---|---|---|---|---|---|---|---|
| burst | gbdt | 100 | 1.1001 | 0.4783 | 3.3007 | 3.4518 | 4.1259 |
| burst | hw_period_6 | 100 | 1.483 | 0.7279 | 3.8164 | 4.6491 | 5.6866 |
| burst | hw_train_selected | 100 | 1.4747 | 0.715 | 3.8049 | 4.6366 | 5.6641 |
| burst | moving_average_6 | 100 | 1.8154 | 0.9561 | 4.7579 | 5.2814 | 6.7677 |
| burst | persistence | 100 | 1.0375 | 0.525 | 3.4871 | 2.999 | 3.9761 |
| chaotic | gbdt | 100 | 4.0876 | 2.8209 | 6.7882 | 19.0639 | 18.2822 |
| chaotic | hw_period_6 | 100 | 3.1888 | 1.7151 | 6.2507 | 18.6342 | 12.7236 |
| chaotic | hw_train_selected | 100 | 3.2161 | 1.7286 | 6.2653 | 18.7275 | 12.945 |
| chaotic | moving_average_6 | 100 | 3.1376 | 1.868 | 6.8555 | 20.3912 | 12.4691 |
| chaotic | persistence | 100 | 2.67 | 1.5602 | 5.8496 | 17.5251 | 10.1561 |
| growing | gbdt | 100 | 9.7116 | 1.1555 | 11.3233 | 10.4144 | 10.7978 |
| growing | hw_period_6 | 100 | 0.4593 | 0.1469 | 0.63 | 0.5145 | 0.5107 |
| growing | hw_train_selected | 100 | 0.4593 | 0.1469 | 0.63 | 0.5145 | 0.5107 |
| growing | moving_average_6 | 100 | 0.574 | 0.2021 | 0.728 | 0.6432 | 0.6384 |
| growing | persistence | 100 | 0.3659 | 0.1457 | 0.6153 | 0.4102 | 0.4068 |
| onoff | gbdt | 100 | 5.5859 | 3.8955 | 10.1338 | 27.3314 | 12.5118 |
| onoff | hw_period_6 | 100 | 7.6861 | 5.2098 | 13.5272 | 34.8917 | 16.9982 |
| onoff | hw_train_selected | 100 | 6.7986 | 5.6673 | 11.4315 | 29.6169 | 14.5149 |
| onoff | moving_average_6 | 100 | 7.2112 | 4.2039 | 13.9889 | 43.2625 | 16.5147 |
| onoff | persistence | 100 | 6.3442 | 4.8335 | 12.9968 | 31.2149 | 13.8656 |
| seasonal | gbdt | 100 | 0.5326 | 0.1573 | 0.6984 | 1.6919 | 1.49 |
| seasonal | hw_period_6 | 100 | 0.8248 | 0.3789 | 1.0223 | 2.6587 | 2.3291 |
| seasonal | hw_train_selected | 100 | 0.6571 | 0.1757 | 0.8447 | 2.0896 | 1.842 |
| seasonal | moving_average_6 | 100 | 2.8762 | 1.6144 | 3.2622 | 9.0374 | 8.1483 |
| seasonal | persistence | 100 | 0.9712 | 0.4443 | 1.2483 | 3.0514 | 2.7458 |
| stepped | gbdt | 100 | 0.7577 | 0.3584 | 2.3935 | 2.1209 | 1.5592 |
| stepped | hw_period_6 | 100 | 0.9278 | 0.4536 | 2.6354 | 2.8527 | 1.9303 |
| stepped | hw_train_selected | 100 | 0.8941 | 0.4597 | 2.6323 | 2.7169 | 1.8581 |
| stepped | moving_average_6 | 100 | 0.883 | 0.3918 | 3.4158 | 2.9598 | 1.8579 |
| stepped | persistence | 100 | 0.6099 | 0.369 | 2.4721 | 1.8342 | 1.262 |

## Horizon 4 steps

| pattern | model | scenarios | mae | mae_sd | rmse | mape_nonzero | wape |
|---|---|---|---|---|---|---|---|
| burst | gbdt | 100 | 2.2975 | 1.2017 | 5.4333 | 7.0162 | 8.4857 |
| burst | hw_period_6 | 100 | 3.4596 | 1.8389 | 8.2092 | 10.9878 | 13.1403 |
| burst | hw_train_selected | 100 | 3.4588 | 1.8669 | 8.1922 | 11.0346 | 13.1658 |
| burst | moving_average_6 | 100 | 2.6884 | 1.4883 | 6.1635 | 7.87 | 9.863 |
| burst | persistence | 100 | 2.3157 | 1.2946 | 6.2151 | 6.673 | 8.6699 |
| chaotic | gbdt | 100 | 8.086 | 6.064 | 11.8035 | 32.7522 | 39.1217 |
| chaotic | hw_period_6 | 100 | 5.8865 | 3.2577 | 11.2702 | 32.7537 | 23.8688 |
| chaotic | hw_train_selected | 100 | 5.9121 | 3.2467 | 11.2871 | 32.9144 | 24.4116 |
| chaotic | moving_average_6 | 100 | 4.2014 | 2.5207 | 8.9381 | 27.5539 | 17.2252 |
| chaotic | persistence | 100 | 4.1074 | 2.4735 | 8.8346 | 26.5739 | 16.3367 |
| growing | gbdt | 100 | 10.1026 | 1.0637 | 11.6508 | 10.8484 | 11.2271 |
| growing | hw_period_6 | 100 | 0.7021 | 0.1484 | 0.8795 | 0.7857 | 0.7804 |
| growing | hw_train_selected | 100 | 0.7021 | 0.1484 | 0.8795 | 0.7857 | 0.7804 |
| growing | moving_average_6 | 100 | 0.9225 | 0.3958 | 1.1129 | 1.0329 | 1.0255 |
| growing | persistence | 100 | 0.6371 | 0.2363 | 0.8846 | 0.7135 | 0.7083 |
| onoff | gbdt | 100 | 7.6591 | 4.2647 | 12.6648 | 39.7563 | 18.0737 |
| onoff | hw_period_6 | 100 | 12.8403 | 6.8238 | 20.7152 | 62.22 | 29.6149 |
| onoff | hw_train_selected | 100 | 9.4738 | 7.6243 | 15.1906 | 38.1545 | 20.244 |
| onoff | moving_average_6 | 100 | 10.1131 | 5.4217 | 18.5409 | 63.5438 | 23.6549 |
| onoff | persistence | 100 | 8.9715 | 5.3496 | 17.5646 | 52.52 | 20.4628 |
| seasonal | gbdt | 100 | 0.6243 | 0.2431 | 0.8425 | 1.9617 | 1.742 |
| seasonal | hw_period_6 | 100 | 2.2752 | 2.1224 | 2.6553 | 7.3656 | 6.47 |
| seasonal | hw_train_selected | 100 | 0.9925 | 0.2722 | 1.2804 | 3.1172 | 2.7801 |
| seasonal | moving_average_6 | 100 | 5.178 | 2.8301 | 5.8064 | 16.4278 | 14.6693 |
| seasonal | persistence | 100 | 3.2914 | 1.8865 | 3.7505 | 10.3435 | 9.3275 |
| stepped | gbdt | 100 | 1.3333 | 0.5637 | 3.8943 | 3.7335 | 2.7339 |
| stepped | hw_period_6 | 100 | 1.8609 | 0.7875 | 4.8913 | 5.9466 | 3.8998 |
| stepped | hw_train_selected | 100 | 1.8233 | 0.7764 | 4.8813 | 5.808 | 3.8292 |
| stepped | moving_average_6 | 100 | 1.289 | 0.6094 | 4.7515 | 4.48 | 2.7197 |
| stepped | persistence | 100 | 0.9876 | 0.491 | 4.1321 | 3.2646 | 2.0659 |

## Paired comparisons against persistence

Negative MAE delta favors the model; wins count strict improvements over the same scenario. These descriptive comparisons do not treat time points as independent replicates.

| pattern | horizon_steps | model | mae_delta_mean | mae_delta_sd | wins | ties | n |
|---|---|---|---|---|---|---|---|
| burst | 1 | moving_average_6 | 0.7779 | 0.5619 | 0 | 0 | 100 |
| burst | 1 | hw_period_6 | 0.4456 | 0.2369 | 0 | 0 | 100 |
| burst | 1 | hw_train_selected | 0.4372 | 0.2247 | 0 | 0 | 100 |
| burst | 1 | gbdt | 0.0626 | 0.209 | 33 | 0 | 100 |
| burst | 4 | moving_average_6 | 0.3727 | 0.3499 | 15 | 0 | 100 |
| burst | 4 | hw_period_6 | 1.1438 | 0.662 | 0 | 0 | 100 |
| burst | 4 | hw_train_selected | 1.143 | 0.6808 | 0 | 0 | 100 |
| burst | 4 | gbdt | -0.0182 | 0.4378 | 51 | 0 | 100 |
| chaotic | 1 | moving_average_6 | 0.4676 | 0.4981 | 16 | 0 | 100 |
| chaotic | 1 | hw_period_6 | 0.5187 | 0.2224 | 0 | 0 | 100 |
| chaotic | 1 | hw_train_selected | 0.5461 | 0.26 | 0 | 0 | 100 |
| chaotic | 1 | gbdt | 1.4176 | 2.7733 | 14 | 0 | 100 |
| chaotic | 4 | moving_average_6 | 0.0939 | 0.2856 | 34 | 0 | 100 |
| chaotic | 4 | hw_period_6 | 1.7791 | 0.8556 | 0 | 0 | 100 |
| chaotic | 4 | hw_train_selected | 1.8046 | 0.8582 | 0 | 0 | 100 |
| chaotic | 4 | gbdt | 3.9786 | 6.2679 | 11 | 0 | 100 |
| growing | 1 | moving_average_6 | 0.2082 | 0.1756 | 10 | 0 | 100 |
| growing | 1 | hw_period_6 | 0.0934 | 0.0093 | 0 | 0 | 100 |
| growing | 1 | hw_train_selected | 0.0934 | 0.0093 | 0 | 0 | 100 |
| growing | 1 | gbdt | 9.3457 | 1.1741 | 0 | 0 | 100 |
| growing | 4 | moving_average_6 | 0.2854 | 0.1863 | 8 | 0 | 100 |
| growing | 4 | hw_period_6 | 0.065 | 0.1885 | 33 | 0 | 100 |
| growing | 4 | hw_train_selected | 0.065 | 0.1885 | 33 | 0 | 100 |
| growing | 4 | gbdt | 9.4654 | 1.2705 | 0 | 0 | 100 |
| onoff | 1 | moving_average_6 | 0.867 | 1.6025 | 28 | 0 | 100 |
| onoff | 1 | hw_period_6 | 1.3419 | 0.481 | 0 | 0 | 100 |
| onoff | 1 | hw_train_selected | 0.4544 | 1.0786 | 40 | 0 | 100 |
| onoff | 1 | gbdt | -0.7583 | 1.3852 | 69 | 0 | 100 |
| onoff | 4 | moving_average_6 | 1.1415 | 1.4227 | 22 | 0 | 100 |
| onoff | 4 | hw_period_6 | 3.8688 | 1.6346 | 0 | 0 | 100 |
| onoff | 4 | hw_train_selected | 0.5023 | 3.5393 | 45 | 0 | 100 |
| onoff | 4 | gbdt | -1.3124 | 3.1562 | 65 | 0 | 100 |
| seasonal | 1 | moving_average_6 | 1.9051 | 1.1952 | 0 | 0 | 100 |
| seasonal | 1 | hw_period_6 | -0.1463 | 0.1318 | 83 | 0 | 100 |
| seasonal | 1 | hw_train_selected | -0.3141 | 0.4637 | 83 | 0 | 100 |
| seasonal | 1 | gbdt | -0.4386 | 0.4878 | 100 | 0 | 100 |
| seasonal | 4 | moving_average_6 | 1.8866 | 0.9473 | 0 | 0 | 100 |
| seasonal | 4 | hw_period_6 | -1.0162 | 0.4914 | 100 | 0 | 100 |
| seasonal | 4 | hw_train_selected | -2.2989 | 1.9664 | 100 | 0 | 100 |
| seasonal | 4 | gbdt | -2.6671 | 1.985 | 100 | 0 | 100 |
| stepped | 1 | moving_average_6 | 0.2731 | 0.2246 | 6 | 0 | 100 |
| stepped | 1 | hw_period_6 | 0.318 | 0.1137 | 0 | 0 | 100 |
| stepped | 1 | hw_train_selected | 0.2842 | 0.1234 | 0 | 0 | 100 |
| stepped | 1 | gbdt | 0.1479 | 0.1127 | 2 | 0 | 100 |
| stepped | 4 | moving_average_6 | 0.3013 | 0.2096 | 5 | 0 | 100 |
| stepped | 4 | hw_period_6 | 0.8732 | 0.3162 | 0 | 0 | 100 |
| stepped | 4 | hw_train_selected | 0.8357 | 0.3057 | 0 | 0 | 100 |
| stepped | 4 | gbdt | 0.3456 | 0.2589 | 6 | 0 | 100 |

Models: persistence; mean of six preceding samples; additive Holt–Winters (alpha .9, beta .2, gamma .3), fixed period 6 or period selected from 6/12/24/48/96 using final 20% of training MAE separately per horizon; histogram GBDT with 24 lag features, 60 iterations, 15 leaves, learning rate .1, seed 0, no early stopping. Predictions are clipped at zero. HW initialization uses the first two training seasons. No filename-derived period or pattern label enters model fitting. These implementations and horizons differ from the paper; no direct reproduction of its +37.4% claim is asserted.
