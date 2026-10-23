# Growing dataset provenance and frozen replay

Frozen before controller execution.

The source is `data/phpa/phpa-datasets/growing_1_growth_rate0.08_seasonality_strength0.6_cyclic_growthFalse_base_level20_noise_level0.3_test.csv` (SHA-256 `7906881e6b7967b1fbad62864d8b5889e55a502ff5aa37aec77b4afc46eaa66f`). It contains 672 released synthetic `pod_count` observations at a complete 15-minute cadence. The values are a generated pod-demand proxy, not observed HTTP requests or measured live replicas.

The deterministic selection first chooses scenario 1 because it is the lowest numeric non-cyclic growing test scenario. It then evaluates every contiguous 42-observation window in that one scenario and selects the earliest window with the maximum ordinary least-squares slope: source indices 463–504, `2024-02-02 19:45:00` through `2024-02-03 06:00:00`. Values range from 90 to 99, the fitted slope is 0.203954299 pods per observation (0.815817195 per source hour), and the late-third mean exceeds the early-third mean by 5.714286. This outcome-independent rule intentionally identifies a sustained-growth episode without using controller results.

Each observed 15-minute interval is held for 10 replay seconds, a constant 90× acceleration. No intermediate source observations are invented. The affine proxy `target_rps = 20 + 100 × (pod_count − 90) / 9` spans the previously validated 20–120 requests/s benchmark envelope and is identical for all controllers. It is not a reconstruction of original traffic. The 420-second measurement provides 28 nominal Metrics Server/HPA resolutions and 42 PHPA sync periods; interpretation is limited to the sustained ramp, not individual 10-second steps or native-time behavior.

The scheduled measurement contains 30733 requests. The replay SHA-256 is `2eff7038f6ae6b6bb2ee60e4d5a0aad13e77f425b48b5f06e8fd33fd0f123d6d` and canonical deterministic schedule SHA-256 is `c6a23cdcdf7658fd6b93bb7ae70d52d1c9418c370df38dfc0aef43ce2b524647`.
