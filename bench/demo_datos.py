"""Genera un día de banco SINTÉTICO (verdad + eventos de dos dispositivos) para
probar el informe. Los dispositivos se modelan con latencias, pérdidas y falsas
alarmas inventadas: el resultado no dice nada de ningún producto real.

  python bench/demo_datos.py demo/   y luego   python bench/informe.py --verdad demo/verdad.csv ...
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eventos import DevEvent, Truth, ensure_dir, truth_occupancy, write_dev, write_truth  # noqa: E402

T0 = 1_790_000_000.0   # instante arbitrario


def make(seed: int = 0, hours: float = 24.0):
    rng = np.random.default_rng(seed)
    truth = [Truth(T0, "inicio")]
    t = T0 + 600
    while t < T0 + hours * 3600 - 3600:
        truth.append(Truth(t, "entra", "S01"))
        stay = rng.uniform(300, 3600)
        k = t + rng.uniform(20, 60)
        while k < t + stay - 60:
            act = rng.choice(["sentado", "de_pie", "tumbado", "caida"], p=[.45, .3, .2, .05])
            truth.append(Truth(k, str(act), "S01"))
            if act == "caida":
                truth.append(Truth(k + rng.uniform(20, 40), "levanta", "S01"))
            k += rng.uniform(120, 900)
        t += stay
        truth.append(Truth(t, "sale", "S01"))
        t += rng.uniform(600, 5400)
    truth.append(Truth(T0 + hours * 3600, "fin"))
    occ = truth_occupancy(truth)

    def device(name, lat_in, lat_out, p_lost_min, fa_per_day, p_fall, fall_fa_day):
        ev = [DevEvent(T0, name, "ocupacion", 0), DevEvent(T0, name, "caida", 0)]
        for a, b in occ:
            ev.append(DevEvent(a + abs(rng.normal(lat_in, lat_in / 3)), name, "ocupacion", 1))
            # pérdidas de persona quieta durante la estancia
            m = a + 120
            while m < b - 120:
                if rng.random() < p_lost_min:
                    ev.append(DevEvent(m, name, "ocupacion", 0))
                    ev.append(DevEvent(m + rng.uniform(5, 50), name, "ocupacion", 1))
                m += 60
            ev.append(DevEvent(b + abs(rng.normal(lat_out, lat_out / 3)), name, "ocupacion", 0))
        for _ in range(rng.poisson(fa_per_day * hours / 24)):
            x = rng.uniform(T0, T0 + hours * 3600)
            if not any(a - 60 <= x <= b + 60 for a, b in occ):
                ev += [DevEvent(x, name, "ocupacion", 1), DevEvent(x + rng.uniform(5, 30), name, "ocupacion", 0)]
        for e in truth:
            if e.evento == "caida" and rng.random() < p_fall:
                d = rng.uniform(4, 9)
                ev += [DevEvent(e.t + d, name, "caida", 1), DevEvent(e.t + d + 60, name, "caida", 0)]
        for _ in range(rng.poisson(fall_fa_day * hours / 24)):
            x = rng.uniform(T0, T0 + hours * 3600)
            ev += [DevEvent(x, name, "caida", 1), DevEvent(x + 60, name, "caida", 0)]
        return ev

    events = (device("prototipo", 0.6, 2.5, 0.0005, 0.3, 0.93, 0.05)
              + device("referencia", 0.9, 4.0, 0.006, 1.5, 0.0, 0.0))
    return truth, events


if __name__ == "__main__":
    out = ensure_dir(sys.argv[1] if len(sys.argv) > 1 else "demo")
    truth, events = make()
    write_truth(out / "verdad.csv", truth)
    write_dev(out / "eventos.csv", events)
    print(f"{len(truth)} eventos de verdad, {len(events)} de dispositivos -> {out}")
