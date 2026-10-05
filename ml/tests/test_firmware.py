"""Compila el código C del firmware en el PC y lo compara con la referencia Python."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_host  # noqa: E402


def have_cc() -> bool:
    try:
        build_host.compiler()
        return True
    except SystemExit:
        return False


@unittest.skipUnless(have_cc(), "sin compilador C")
class FirmwareCoreTest(unittest.TestCase):
    def test_contract_decision_limits_in_c(self):
        out = build_host.build("test_host")
        r = subprocess.run([str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
