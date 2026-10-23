import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "guarded_exec", Path(__file__).resolve().parents[1] / "scripts/live/guarded_exec.py")
guarded = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guarded)


class GuardedExecTests(unittest.TestCase):
    def test_parse_cpu_list(self):
        self.assertEqual(guarded.parse_cpu_list("1,3-5"), {1, 3, 4, 5})

    def test_affinity_snapshot_checks_every_thread(self):
        records = guarded.affinity_snapshot(os.getpid())
        self.assertTrue(records)
        self.assertTrue(all(item["allowed_cpus"] for item in records))
        self.assertTrue(all(item["proc_status_cpus_allowed_list"] for item in records))

    def test_subprocess_inherits_scheduler_affinity(self):
        available = sorted(os.sched_getaffinity(0))
        if not available:
            self.skipTest("no schedulable CPU")
        cpu = available[0]
        completed = subprocess.run(
            ["taskset", "--cpu-list", str(cpu), sys.executable, "-c",
             "import os,subprocess,sys; p=subprocess.run([sys.executable,'-c','import os;print(sorted(os.sched_getaffinity(0)))'],capture_output=True,text=True); print(sorted(os.sched_getaffinity(0))); print(p.stdout.strip())"],
            capture_output=True, text=True, check=True)
        self.assertEqual(completed.stdout.strip().splitlines(), [f"[{cpu}]", f"[{cpu}]"])


if __name__ == "__main__":
    unittest.main()
