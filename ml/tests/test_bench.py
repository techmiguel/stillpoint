"""Bench tools: metrics with injected errors of known size."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))

import annotator  # noqa: E402
import ha_export  # noqa: E402
import report  # noqa: E402
from events import DevEvent, Truth, read_truth, truth_occupancy  # noqa: E402

T0 = 1_800_000_000.0


def scenario():
    truth = [Truth(T0, "start"), Truth(T0 + 100, "enter"), Truth(T0 + 200, "fall"),
             Truth(T0 + 400, "leave"), Truth(T0 + 1000, "enter"), Truth(T0 + 1300, "leave"),
             Truth(T0 + 3600, "end")]
    ev = [DevEvent(T0, "d", "occupancy", 0), DevEvent(T0, "d", "fall", 0),
          DevEvent(T0 + 100.5, "d", "occupancy", 1), DevEvent(T0 + 402, "d", "occupancy", 0),
          DevEvent(T0 + 1000.8, "d", "occupancy", 1), DevEvent(T0 + 1303, "d", "occupancy", 0),
          DevEvent(T0 + 207, "d", "fall", 1), DevEvent(T0 + 260, "d", "fall", 0),
          # one false occupancy in the empty room and one false fall alarm
          DevEvent(T0 + 2000, "d", "occupancy", 1), DevEvent(T0 + 2010, "d", "occupancy", 0),
          DevEvent(T0 + 3000, "d", "fall", 1), DevEvent(T0 + 3060, "d", "fall", 0)]
    return truth, ev


class BenchTest(unittest.TestCase):
    def test_occupancy_intervals(self):
        truth, _ = scenario()
        self.assertEqual(truth_occupancy(truth), [(T0 + 100, T0 + 400), (T0 + 1000, T0 + 1300)])

    def test_metrics_with_known_errors(self):
        truth, ev = scenario()
        m = report.metrics_for(truth, ev, "d")
        self.assertAlmostEqual(m["P4"]["value"], 0.5 + 0.95 * 0.3, places=6)   # p95 of [0.5, 0.8]
        self.assertAlmostEqual(m["P5"]["value"], 2 + 0.95 * 1, places=6)       # p95 of [2, 3]
        self.assertEqual((m["F1"]["k"], m["F1"]["n"]), (1, 1))
        self.assertEqual(m["F2"]["n"], 1)
        self.assertEqual(m["P3"]["n"], 1)
        self.assertEqual(m["P1"]["k"], m["P1"]["n"])

    def test_small_n_cannot_pass_rate_criteria(self):
        truth, ev = scenario()
        m = report.metrics_for(truth, [e for e in ev if e.t != T0 + 3000], "d")
        self.assertEqual(m["F2"]["n"], 0)
        self.assertFalse(report.passes("F2", m["F2"]))      # 0 in 1 h does not prove <= 0.1/day
        self.assertFalse(report.passes("F1", m["F1"]))      # 1/1: lower CI bound < 80 %

    def test_annotator_saves_every_key(self):
        with tempfile.TemporaryDirectory() as d:
            clock = iter([T0, T0 + 5, T0 + 9]).__next__
            s = annotator.Session(Path(d) / "v.csv", "S01", clock=clock)
            s.key("e")
            s.key("c")
            s.key("z")
            ev = read_truth(Path(d) / "v.csv")
            self.assertEqual([e.event for e in ev], ["enter"])

    def test_home_assistant_export(self):
        with tempfile.TemporaryDirectory() as d:
            h, mp = Path(d) / "h.csv", Path(d) / "m.csv"
            with open(h, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["entity_id", "state", "last_changed"])
                w.writerow(["binary_sensor.r_occ", "on", "2026-10-05T10:00:00.000Z"])
                w.writerow(["binary_sensor.r_occ", "unavailable", "2026-10-05T10:01:00.000Z"])
                w.writerow(["binary_sensor.fp2", "off", "2026-10-05T10:02:00+00:00"])
                w.writerow(["sensor.other", "3", "2026-10-05T10:03:00Z"])
            with open(mp, "w", newline="") as f:
                f.write("entity_id,device,signal\nbinary_sensor.r_occ,Stillpoint,occupancy\n"
                        "binary_sensor.fp2,aqara_fp2,occupancy\n")
            ev = ha_export.convert(h, mp)
            self.assertEqual([(e.device, e.value) for e in ev], [("Stillpoint", 1.0), ("aqara_fp2", 0.0)])


if __name__ == "__main__":
    unittest.main()
