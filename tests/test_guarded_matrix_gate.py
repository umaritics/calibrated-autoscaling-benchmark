import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "guarded_matrix", Path(__file__).resolve().parents[1] / "scripts/live/run_guarded_chaotic_comparison.py")
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class GuardedMatrixGateTests(unittest.TestCase):
    def test_matrix_latch_requires_resolution_of_exact_block(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            block = out / "BLOCK_NEW_RUNS"
            block.write_text(json.dumps({"blocked_utc": "first"}))
            with mock.patch.object(matrix, "OUT", out):
                self.assertTrue(matrix.block_is_active(block))
                (out / "block_resolution.json").write_text(
                    json.dumps({"resolved_blocked_utc": "different"}))
                self.assertTrue(matrix.block_is_active(block))
                (out / "block_resolution.json").write_text(
                    json.dumps({"resolved_blocked_utc": "first"}))
                self.assertFalse(matrix.block_is_active(block))


if __name__ == "__main__":
    unittest.main()
