import hashlib
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/live_trace_phase/growing_first_comparison"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GrowingComparisonEvidenceTests(unittest.TestCase):
    def test_frozen_trace_and_schedule_hashes(self):
        frozen = json.loads((OUT / "frozen_plan.json").read_text())
        validation = json.loads((OUT / "dataset_validation.json").read_text())
        trace_path = ROOT / frozen["replay_path"]
        self.assertEqual(sha256(trace_path), frozen["replay_sha256"])
        self.assertEqual(frozen["replay_sha256"], validation["selected_window"]["replay_trace_sha256"])
        trace = pd.read_csv(trace_path)
        schedule = [(second + quarter / 4, "warmup") for second in range(120) for quarter in range(4)]
        for index, row in trace.iterrows():
            count = round(float(row.target_rps) * 10)
            schedule.extend((120 + index * 10 + (item + .5) * 10 / count, "measurement")
                            for item in range(count))
        payload = "".join(f"{phase},{planned:.9f}\n" for planned, phase in schedule).encode()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), frozen["expected_schedule_sha256"])
        self.assertEqual(len(schedule) - 480, 30733)

    def test_all_runs_accepted_and_independently_verified(self):
        comparison = json.loads((OUT / "comparison.json").read_text())
        verification = json.loads((OUT / "independent_verification.json").read_text())
        self.assertEqual(comparison["status"], "COMPLETE")
        self.assertEqual(verification["cpu_coverage_threshold"], .90)
        self.assertTrue(verification["acceptance_criteria_unchanged"])
        self.assertEqual(set(verification["run_decisions"].values()), {"ACCEPT"})
        for checks in verification["checks"].values():
            self.assertTrue(all(checks.values()))
        for row in comparison["rows"]:
            self.assertEqual(row["generator_drops"], 0)
            self.assertGreaterEqual(row["cpu_coverage"], .90)

    def test_evidence_manifest_hashes(self):
        manifest = json.loads((OUT / "evidence_manifest.json").read_text())
        self.assertEqual(manifest["algorithm"], "sha256")
        for relative, record in manifest["files"].items():
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(path.stat().st_size, record["bytes"], relative)
            self.assertEqual(sha256(path), record["sha256"], relative)


if __name__ == "__main__":
    unittest.main()
