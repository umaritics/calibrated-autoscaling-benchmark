"""Focused tests for genuine NASA/Alibaba forecast evaluation."""

import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
from threadpoolctl import threadpool_limits


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/real_world_forecasting.py"
SPEC = importlib.util.spec_from_file_location("real_world_forecasting", MODULE_PATH)
forecasting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forecasting)


class RealWorldForecastingTests(unittest.TestCase):
    def test_nasa_timestamp_parsing_and_complete_bin_aggregation(self):
        lines = [
            b'a - - [01/Jul/1995:00:00:01 -0400] "GET /" 200 1\n',
            b'b - - [01/Jul/1995:00:00:01 -0400] "GET /" 200 1\n',
            b'c - - [01/Jul/1995:00:10:00 -0400] "GET /" 200 1\n',
            b'broken final fragment',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "NASA_access_log_Jul95.gz"
            with gzip.open(path, "wb") as handle:
                handle.writelines(lines)
            frame, metadata = forecasting.parse_nasa(path)
            repeated, repeated_metadata = forecasting.parse_nasa(path)
        self.assertEqual(frame.value.tolist(), [2.0, 0.0])
        self.assertTrue(frame.equals(repeated))
        self.assertEqual(metadata, repeated_metadata)
        self.assertEqual(metadata["parsed_requests"], 3)
        self.assertEqual(metadata["unparsed_records"], 1)
        self.assertEqual(metadata["excluded_trailing_partial_bin_requests"], 1)
        self.assertEqual(metadata["zero_request_bins"], 1)

    def test_alibaba_selection_is_earliest_longest_contiguous_run(self):
        counts = {0: 20, 10: 20, 20: 20, 40: 25, 50: 25, 60: 25, 80: 19}
        self.assertEqual(forecasting.select_contiguous_timestamps(counts, 20, 10), (0, 20, 3))

    def test_duplicate_container_timestamp_has_one_contribution(self):
        sums = {}
        counts = forecasting.Counter()
        duplicates, invalid = forecasting._commit_container({10: [20.0, 40.0], 20: [10.0]}, sums, counts)
        self.assertEqual((duplicates, invalid), (1, 0))
        self.assertEqual(sums, {10: 30.0, 20: 10.0})
        self.assertEqual(counts, {10: 1, 20: 1})

    def test_chronological_split_has_no_overlap(self):
        train_end, validation_end = forecasting.chronological_boundaries(101)
        self.assertEqual((train_end, validation_end), (60, 80))
        self.assertLess(train_end - 1, train_end)
        self.assertLess(validation_end - 1, validation_end)

    def test_metric_zero_rules_and_arithmetic(self):
        result = forecasting.metric_values(np.array([0.0, 2.0]), np.array([1.0, 1.0]))
        self.assertEqual(result["mae"], 1.0)
        self.assertEqual(result["rmse"], 1.0)
        self.assertEqual(result["mape_nonzero"], 50.0)
        self.assertEqual(result["mape_defined_pairs"], 1)
        self.assertEqual(result["mape_undefined_zero_pairs"], 1)
        self.assertEqual(result["wape"], 100.0)
        self.assertAlmostEqual(result["smape"], 100 * (2 + 2 / 3) / 2)

    def test_forecast_target_alignment(self):
        values = np.arange(100.0)
        horizon = 6
        origins = np.arange(20, len(values) - horizon + 1)
        targets = origins + horizon - 1
        self.assertEqual(targets[0], 25)
        self.assertEqual(targets[-1], 99)
        np.testing.assert_array_equal(values[origins - 1], np.arange(19.0, 94.0))

    def test_future_values_cannot_change_earlier_predictions(self):
        rng = np.random.default_rng(7)
        base = 20 + rng.normal(size=400)
        changed = base.copy()
        changed[350:] += 1000
        config = {
            "target": "cpu",
            "units": "percent",
            "interval_seconds": 10,
            "horizons": [1, 6],
            "moving_average_window": 6,
            "seasonal_period": None,
            "gbdt_lags": list(range(1, 13)) + [60, 120],
        }
        import pandas as pd
        first = pd.DataFrame({"timestamp": np.arange(400) * 10, "value": base})
        second = pd.DataFrame({"timestamp": np.arange(400) * 10, "value": changed})
        with threadpool_limits(limits=1):
            left, _, _ = forecasting.evaluate_dataset("alibaba", first, config)
            right, _, _ = forecasting.evaluate_dataset("alibaba", second, config)
        left = left[left.target_index < 350].sort_values(["horizon_steps", "model", "target_index"])
        right = right[right.target_index < 350].sort_values(["horizon_steps", "model", "target_index"])
        np.testing.assert_allclose(left.predicted.to_numpy(), right.predicted.to_numpy())


if __name__ == "__main__":
    unittest.main()
