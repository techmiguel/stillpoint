"""Fast tests (< 5 s): contract, data split, decision, metrics, RF limits.

Run from ml/:  python -m unittest discover -s tests -v
"""
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

from radarref import contract as ct
from radarref.config import RadarConfig
from radarref.decision import (F_CONFIRMED, F_NONE, F_SUSPECTED, F_UNCERTAIN, P_UNCERTAIN, Inputs,
                               TrackDecision)
from radarref.metrics import days_needed, match_events, rate_per_day, wilson
from radarref.split import LeakageError, Session, check, split

ROOT = Path(__file__).resolve().parents[2]


class ContractTest(unittest.TestCase):
    def setUp(self):
        self.c = ct.load()

    def test_roundtrip_and_size(self):
        v = np.linspace(-2, 2, self.c.n)
        rec = ct.pack(self.c, 7, 1234, 3, 0, v)
        self.assertEqual(len(rec), self.c.record_size)
        self.assertEqual(self.c.record_size, 66)
        out = ct.unpack(self.c, rec)
        np.testing.assert_allclose(out["values"], v, atol=0.5 / self.c.scales.min() + 1e-9)

    def test_crc_detects_corruption(self):
        rec = bytearray(ct.pack(self.c, 1, 2, 3, 0, np.zeros(self.c.n)))
        rec[20] ^= 1
        with self.assertRaises(ct.RecordError):
            ct.unpack(self.c, bytes(rec))

    def test_saturation_not_wraparound(self):
        q = ct.quantize(self.c, np.full(self.c.n, 1e6))
        self.assertTrue(np.all(q == 32767))

    def test_half_rounds_away_from_zero(self):
        v = np.zeros(self.c.n)
        v[0], v[1] = 0.0005, -0.0005     # scale 1000 -> ±0.5
        q = ct.quantize(self.c, v)
        self.assertEqual((q[0], q[1]), (1, -1))

    def test_hash_changes_with_semantics(self):
        import yaml
        spec = yaml.safe_load(ct.CONTRACT_PATH.read_text(encoding="utf-8"))
        a = ct.canonical_string(spec)
        spec["fields"][0]["scale"] = 100
        self.assertNotEqual(a, ct.canonical_string(spec))

    def test_generated_c_headers_are_current(self):
        before = {p: p.read_bytes() for p in (ROOT / "firmware").rglob("*.h")
                  if p.name in ("features_v1.h", "golden_v1.h", "decision_vectors.h")}
        subprocess.run([sys.executable, str(ROOT / "tools" / "gen_contract.py")], check=True,
                       capture_output=True)
        for p, b in before.items():
            self.assertEqual(p.read_bytes(), b, f"{p.name} is stale: run tools/gen_contract.py")


class SplitTest(unittest.TestCase):
    def test_disjoint_by_subject_and_room(self):
        s = [Session(f"{a}{r}", a, r) for a in "ABCDE" for r in "xyz"]
        p = split(s, test_subjects=["E"], test_rooms=["z"], val_subjects=["D"], val_rooms=["y"])
        self.assertEqual({x.id for x in p["test"]}, {"Ez"})
        self.assertTrue(all(x.subject in "ABC" and x.room == "x" for x in p["train"]))

    def test_leak_is_detected(self):
        with self.assertRaises(LeakageError):
            check({"train": [Session("1", "A", "x")], "test": [Session("2", "A", "y")]})


class DecisionTest(unittest.TestCase):
    def run_seq(self, seq):
        d = TrackDecision()
        return [d.update(x) for x in seq]

    def test_fall_is_confirmed(self):
        seq = [Inputs(t * .5, (.9, .05, .05, 0) if t < 10 else (.1, 0, .1, .8) if t < 14 else (0, 0, 1, 0),
                      1.2 if t < 10 else .3, -1.5 if 10 <= t < 12 else 0, max(0, t * .5 - 7), .8, False, 0)
               for t in range(40)]
        falls = [f for _, _, f in self.run_seq(seq)]
        self.assertIn(F_SUSPECTED, falls)
        self.assertEqual(falls[-1], F_CONFIRMED)

    def test_getting_up_cancels(self):
        seq = [Inputs(t * .5, (.1, 0, .1, .8), .3, -1.2, 0, .8, False, 0) for t in range(4)]
        seq += [Inputs(t * .5, (.9, .05, .05, 0), 1.4, 0, 0, .8, False, 0) for t in range(4, 10)]
        self.assertEqual(self.run_seq(seq)[-1][2], F_NONE)

    def test_occlusion_during_suspicion_is_uncertain_not_silent(self):
        seq = [Inputs(0, (.1, 0, .1, .8), .3, -1.2, 0, .8, False, 0),
               Inputs(.5, (.1, 0, .1, .8), .3, -1.2, 0, .8, True, 0)]
        self.assertEqual(self.run_seq(seq)[-1][2], F_UNCERTAIN)

    def test_low_confidence_posture_is_declared(self):
        post, _, _ = TrackDecision().update(Inputs(0, (.4, .35, .25, 0), 1.2, 0, 5, .9, False, 0))
        self.assertEqual(post, P_UNCERTAIN)

    def test_out_of_distribution_is_declared(self):
        post, _, _ = TrackDecision().update(Inputs(0, (.95, .03, .02, 0), 1.2, 0, 5, .9, False, 6))
        self.assertEqual(post, P_UNCERTAIN)


class MetricsTest(unittest.TestCase):
    def test_wilson(self):
        p, lo, hi = wilson(90, 100)
        self.assertAlmostEqual(p, .9)
        self.assertTrue(.82 < lo < .84 and .94 < hi < .96)

    def test_rule_of_three(self):
        self.assertAlmostEqual(days_needed(0.1), 29.96, places=1)
        _, lo, hi = rate_per_day(0, 30 * 24)
        self.assertEqual(lo, 0)
        self.assertAlmostEqual(hi, 3.689 / 30, places=3)   # two-sided 95 %

    def test_event_matching(self):
        k, lat, fp = match_events([10, 50], [12, 30, 51], max_latency_s=10)
        self.assertEqual((k, fp), (2, 1))
        np.testing.assert_allclose(lat, [2, 1])


class RadioLimitsTest(unittest.TestCase):
    def test_default_config_is_eu_compliant(self):
        cfg = RadarConfig()
        cfg.check_eu()
        self.assertAlmostEqual(cfg.range_res, 0.12, places=2)
        self.assertGreater(cfg.v_max, 3.0)

    def test_out_of_band_rejected(self):
        with self.assertRaises(ValueError):
            RadarConfig(f_start_hz=63.0e9, bandwidth_hz=1.5e9).check_eu()
        with self.assertRaises(ValueError):
            RadarConfig(eirp_dbm=21).check_eu()


if __name__ == "__main__":
    unittest.main()
