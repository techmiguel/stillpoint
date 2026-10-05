"""Pruebas de regresión de escenarios (simulación completa, ~1-2 min).

Cada una fija un fallo conocido de los sensores comerciales. Si una cambia,
la figura correspondiente (plot_scenarios.py) muestra por qué.
"""
import unittest

import numpy as np

from radarref import scenarios
from radarref.pipeline import run_scene
from radarref.sim import Simulator
from radarref.tracker import INTERFERER, OCCLUDED


def run(name):
    scene, dur, truth = scenarios.ALL[name]()
    outs = run_scene(Simulator(scene), dur)
    return outs, truth


class ScenarioTest(unittest.TestCase):
    def test_still_person_survives_occlusion(self):
        outs, truth = run("occlusion")
        counts = np.array([o.count for o in outs])
        t = np.array([o.t for o in outs])
        # desde que B está confirmado, la sala nunca se declara vacía
        first = np.argmax(counts > 0)
        self.assertTrue(np.all(counts[first:] >= 1), "la persona quieta desapareció")
        # durante la oclusión hay dos personas y B figura como ocluida, no borrada
        mid = (t > 25) & (t < 35)
        self.assertTrue(np.all(counts[mid] == 2))
        self.assertTrue(any(st == OCCLUDED for o in outs if 25 < o.t < 35 for _, st, _ in o.tracks))
        # al salir A, vuelve a 1 en menos de 3 s
        self.assertTrue(np.all(counts[t > 42.5] == 1))
        err = np.mean(counts != np.array([truth(x) for x in t]))
        self.assertLess(err, 0.10)

    def test_fan_becomes_interferer(self):
        outs, _ = run("fan_empty")
        late = [o for o in outs if o.t > 25]
        self.assertTrue(all(o.count == 0 for o in late))
        self.assertTrue(any(st == INTERFERER for o in late for _, st, _ in o.tracks))

    def test_mirror_ghost_not_counted(self):
        outs, _ = run("mirror")
        counts = np.array([o.count for o in outs if o.t > 1.0])
        self.assertLess(np.mean(counts != 1), 0.05)

    def test_presence_latency(self):
        outs, _ = run("fall")
        first = next(o.t for o in outs if o.count > 0)
        self.assertLessEqual(first, 1.0)   # criterio P4: entrada -> ocupado <= 1 s


if __name__ == "__main__":
    unittest.main()
