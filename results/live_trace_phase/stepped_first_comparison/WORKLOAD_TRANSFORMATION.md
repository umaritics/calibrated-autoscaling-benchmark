# Stepped dataset provenance and frozen replay

Frozen before controller execution. The source is `data/phpa/phpa-datasets/stepped_62_min_pods20_max_pods70_step_count5_step_duration10_step_typerandom_transition_noise0.4_test.csv` (SHA-256 `b390e57626b38cdb55efb1438033e0d5fd90703aa6950c961070ce8d98630201`), with 672 synthetic `pod_count` observations at 15-minute cadence. These are demand proxies, not observed HTTP requests.

The deterministic selection rule in `dataset_validation.json` selected scenario 62, indices 72–191, containing three complete 10-source-hour plateaus and two opposite material transitions. At 90× acceleration, each observation is held for 10 seconds and each plateau lasts 400 seconds. The 1,200-second measurement is longer than prior 420-second comparisons specifically so the unchanged 300-second tuned-HPA stabilization can be observed; timing was frozen for every arm before execution.

The mapping is `target_rps = 20 + 100 * (pod_count - 18) / (74 - 18)` over the same 20–120 RPS envelope used by growing/on-off. No interpolation or future observation is supplied to any controller. Replay SHA-256: `1d8d830e62ee83af2c2e74b03e8c5a9107190959732ee1e7fb52de7d666fa10e`. Canonical request-schedule SHA-256: `3120b888dac1f2da8d00eebe9fe856ffbf3ded977aa9109d0b8e26334f463f6f`. Scheduled measurement requests: 84578.
