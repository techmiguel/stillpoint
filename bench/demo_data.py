"""Generates one SYNTHETIC bench day (truth + events from two devices) to
exercise the report. The devices are modelled with made-up latencies, dropouts
and false alarms: the result says nothing about any real product.

  python bench/demo_data.py demo/   then   python bench/report.py --truth demo/truth.csv ...
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from events import DevEvent, Truth, ensure_dir, truth_occupancy, write_dev, write_truth  # noqa: E402

T0 = 1_790_000_000.0   # arbitrary instant


def make(seed: int = 0, hours: float = 24.0):
    rng = np.random.default_rng(seed)
    truth = [Truth(T0, "start")]
    t = T0 + 600
    while t < T0 + hours * 3600 - 3600:
        truth.append(Truth(t, "enter", "S01"))
        stay = rng.uniform(300, 3600)
        k = t + rng.uniform(20, 60)
        while k < t + stay - 60:
            act = rng.choice(["sitting", "standing", "lying", "fall"], p=[.45, .3, .2, .05])
            truth.append(Truth(k, str(act), "S01"))
            if act == "fall":
                truth.append(Truth(k + rng.uniform(20, 40), "get_up", "S01"))
            k += rng.uniform(120, 900)
        t += stay
        truth.append(Truth(t, "leave", "S01"))
        t += rng.uniform(600, 5400)
    truth.append(Truth(T0 + hours * 3600, "end"))
    occ = truth_occupancy(truth)

    def device(name, lat_in, lat_out, p_lost_min, fa_per_day, p_fall, fall_fa_day):
        ev = [DevEvent(T0, name, "occupancy", 0), DevEvent(T0, name, "fall", 0)]
        for a, b in occ:
            ev.append(DevEvent(a + abs(rng.normal(lat_in, lat_in / 3)), name, "occupancy", 1))
            # still-person dropouts during the stay
            m = a + 120
            while m < b - 120:
                if rng.random() < p_lost_min:
                    ev.append(DevEvent(m, name, "occupancy", 0))
                    ev.append(DevEvent(m + rng.uniform(5, 50), name, "occupancy", 1))
                m += 60
            ev.append(DevEvent(b + abs(rng.normal(lat_out, lat_out / 3)), name, "occupancy", 0))
        for _ in range(rng.poisson(fa_per_day * hours / 24)):
            x = rng.uniform(T0, T0 + hours * 3600)
            if not any(a - 60 <= x <= b + 60 for a, b in occ):
                ev += [DevEvent(x, name, "occupancy", 1), DevEvent(x + rng.uniform(5, 30), name, "occupancy", 0)]
        for e in truth:
            if e.event == "fall" and rng.random() < p_fall:
                d = rng.uniform(4, 9)
                ev += [DevEvent(e.t + d, name, "fall", 1), DevEvent(e.t + d + 60, name, "fall", 0)]
        for _ in range(rng.poisson(fall_fa_day * hours / 24)):
            x = rng.uniform(T0, T0 + hours * 3600)
            ev += [DevEvent(x, name, "fall", 1), DevEvent(x + 60, name, "fall", 0)]
        return ev

    events = (device("prototype", 0.6, 2.5, 0.0005, 0.3, 0.93, 0.05)
              + device("reference", 0.9, 4.0, 0.006, 1.5, 0.0, 0.0))
    return truth, events


if __name__ == "__main__":
    out = ensure_dir(sys.argv[1] if len(sys.argv) > 1 else "demo")
    truth, events = make()
    write_truth(out / "truth.csv", truth)
    write_dev(out / "events.csv", events)
    print(f"{len(truth)} truth events, {len(events)} device events -> {out}")
