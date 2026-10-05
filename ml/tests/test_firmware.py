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

    def test_int8_inference_matches_tflite(self):
        out = build_host.build("test_nn")
        r = subprocess.run([str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_full_app_matches_python_end_to_end(self):
        sys.path.insert(0, str(ROOT / "ml"))
        import compare_app
        from radarref.classifier import Classifier
        exe = build_host.build("replay_app")
        clf = Classifier(compare_app.ART)
        scene, dur = compare_app.all_scenes()["caida"]
        r = compare_app.run("caida", scene, dur, exe, clf)
        self.assertEqual(r["recuento_igual"], 1.0)
        self.assertEqual(r["postura_y_caida_iguales"], 1.0)
        self.assertEqual(r["alarma_C_s"], r["alarma_python_s"])
        self.assertIsNotNone(r["alarma_C_s"])

    def test_dsp_and_tracker_match_python(self):
        sys.path.insert(0, str(ROOT / "ml"))
        import compare_c
        exe = build_host.build("replay")
        for name in ("fall", "mirror"):
            r = compare_c.run(name, exe)
            self.assertEqual(r["recuento_igual"], 1.0, name)
            self.assertGreaterEqual(r["valores_cuantizados_identicos"], 0.99, name)


if __name__ == "__main__":
    unittest.main()
