# Automated and independent verification coverage

`tests/test_real_world_forecasting.py` contains seven focused tests covering:

1. NASA timestamp parsing, repeated timestamps, zero-bin aggregation, trailing partial-bin exclusion, and deterministic repeated preprocessing.
2. Alibaba earliest-longest contiguous-window selection and contributor threshold.
3. Duplicate container/timestamp handling without overweighting a container.
4. Non-overlapping chronological 60/20/20 boundaries.
5. MAE, RMSE, nonzero-only MAPE, WAPE, sMAPE, and explicit zero counts.
6. Multi-step origin/target alignment.
7. Leakage prevention by mutating future values and comparing all prior forecasts from all four models.

The complete repository suite passes 28/28 tests. The separate
`scripts/verify_real_world_forecasting.py` implementation does not import the
evaluator's metric functions. It independently recomputes all 16 metric groups
from 18,224 retained prediction rows and validates source hashes, observation
counts, splits, native cadence, contributor floor, horizons, target alignment,
metric denominators, common model targets, selected hyperparameters, and output
consistency. Its machine-readable result is `independent_verification.json`.
