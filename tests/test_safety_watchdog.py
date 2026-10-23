import importlib.util
import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "safety_watchdog", Path(__file__).resolve().parents[1] / "scripts/live/safety_watchdog.py")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


class SafetyWatchdogTests(unittest.TestCase):
    def thresholds(self):
        return {
            "load1_max": 6, "cpu_utilization_percent_max": 92,
            "memory_available_bytes_min": 4_000, "memory_psi_full_avg10_max": 1,
            "io_psi_full_avg10_max": 5, "cpu_psi_some_avg10_max": 60,
            "swap_used_bytes_max": 1_000, "disk_free_bytes_min": 4_000,
            "generator_in_flight_max": 240, "workload_ready_replicas_min": 1,
        }

    def safe_record(self):
        return {"load1": 1, "cpu_utilization_percent": 20,
                "memory_available_bytes": 8_000, "memory_psi_full_avg10": 0,
                "io_psi_full_avg10": 0, "cpu_psi_some_avg10": 1,
                "swap_used_bytes": 0, "disk_free_bytes": 8_000,
                "generator_in_flight": 10, "generator_active": True,
                "workload": {"query_ok": True, "ready_replicas": 1}}

    def test_threshold_evaluation_names_exact_reasons(self):
        record = self.safe_record()
        record["memory_available_bytes"] = 3_999
        record["generator_in_flight"] = 241
        self.assertEqual(watchdog.violations(record, self.thresholds()),
                         ["memory_available_low", "generator_in_flight_high"])

    def test_unhealthy_workload_only_matters_during_active_run(self):
        record = self.safe_record()
        record["workload"] = {"query_ok": True, "ready_replicas": 0}
        self.assertIn("workload_unhealthy", watchdog.violations(record, self.thresholds()))
        record["generator_active"] = False
        self.assertNotIn("workload_unhealthy", watchdog.violations(record, self.thresholds()))

    def test_termination_stops_benchmark_process_group(self):
        child = subprocess.Popen(["sleep", "60"], start_new_session=True)
        try:
            result = watchdog.terminate_target({"pid": child.pid, "pgid": child.pid}, 2)
            child.wait(timeout=3)
            self.assertTrue(result["term_sent"])
            self.assertFalse(result["forced"])
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)

    def test_atomic_json_preserves_abort_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "abort.json"
            watchdog.atomic_json(target, {"decision": "SAFETY_ABORTED", "reasons": ["disk_free_low"]})
            self.assertEqual(json.loads(target.read_text())["reasons"], ["disk_free_low"])


if __name__ == "__main__":
    unittest.main()
