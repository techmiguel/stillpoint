"""Event-level evaluation (what the user will see in Matter), not window-level.

Runs scenarios with a TEST person and room (never seen in training): a fall,
lying down in bed and crouching. Plots the timeline and returns whether a fall
was confirmed and with what latency.

Usage: python eval_events.py --model artifacts/synth_v1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from make_synth_dataset import ROOMS, SUBJECTS  # noqa: E402
from radarref.classifier import Classifier, Inference  # noqa: E402
from radarref.config import Room  # noqa: E402
from radarref.decision import F_CONFIRMED  # noqa: E402
from radarref.pipeline import Pipeline  # noqa: E402
from radarref.sim import Person, Scene, Simulator  # noqa: E402

SUBJ, ROOM = "S10", "R3"   # both belong to the test partition
FALL_NAMES = ["none", "suspected", "confirmed", "uncertain"]
POST_NAMES = ["uncertain", "standing", "sitting", "lying"]


def scenes():
    walk = [(0, 1.8, 0, "standing"), (3, 0.4, -0.4, "standing")]
    return {
        "fall": ([*walk, (5, 0.4, -0.4, "standing"), (5.8, 0.4, -0.4, "lying", 0.8), (30, 0.4, -0.4, "lying")], [5.0]),
        "bed": ([*walk, (5, 0.4, -0.4, "standing"), (7, 0.4, -0.4, "sitting", 1.5),
                  (9.5, 0.4, -0.4, "lying_bed", 2.0), (30, 0.4, -0.4, "lying_bed")], []),
        "crouch": ([*walk, (5, 0.4, -0.4, "standing"), (5.8, 0.4, -0.4, "sitting", 0.8),
                       (7, 0.4, -0.4, "sitting"), (7.8, 0.4, -0.4, "standing", 0.8), (12, -1.0, 1.0, "standing"),
                       (30, -1.0, 1.0, "standing")], []),
    }


def run(model_dir: str, out: Path):
    clf = Classifier(model_dir)
    fig, axes = plt.subplots(3, 3, figsize=(14, 8), sharex=True)
    results = {}
    for col, (name, (keys, falls)) in enumerate(scenes().items()):
        rp = ROOMS[ROOM]
        room = Room(mount_h=rp["mount_h"])
        person = Person(keys, fall_times=falls, **SUBJECTS[SUBJ])
        sim = Simulator(Scene(room=room, people=[person], clutter=rp["clutter"], seed=99 + col))
        pipe, inf = Pipeline(room, sim.cfg), Inference(clf)
        T, Z, VZ, PF, FS, PS = [], [], [], [], [], []
        for i in range(300):
            t = i / 10
            o = pipe.step(t, sim.frame(t))
            res = inf.step(o)
            if not o.tracks:
                continue
            tid, _, f = o.tracks[0]
            T.append(t)
            Z.append(f[pipe.c.index("z_centroid")])
            VZ.append(f[pipe.c.index("vz")])
            r = res.get(tid)
            PF.append(r[0][3] if r else np.nan)
            PS.append(r[1] if r else 0)
            FS.append(r[3] if r else 0)
        FS = np.array(FS)
        conf_t = [T[i] for i in range(len(T)) if FS[i] == F_CONFIRMED]
        first = conf_t[0] if conf_t else None
        results[name] = {"real_fall": bool(falls), "confirmed": first is not None,
                         "latency_s": None if (first is None or not falls) else round(first - falls[0], 1)}
        ax = axes[0, col]
        ax.plot(T, Z, label="z centroid (m)")
        ax.plot(T, VZ, label="vz (m/s)", alpha=.7)
        ax.axhline(0.7, ls=":", c="gray")
        for ft in falls:
            ax.axvspan(ft, ft + 0.8, color="tab:red", alpha=.2, label="real fall")
        ax.set_title(f"{name}  (person {SUBJ}, room {ROOM}: unseen)")
        ax.legend(fontsize=7)
        axes[1, col].plot(T, PF, c="tab:red")
        axes[1, col].axhline(0.5, ls=":", c="gray")
        axes[1, col].set_ylim(-.05, 1.05)
        axes[1, col].set_ylabel("p(fall)")
        axes[2, col].step(T, FS, where="post", c="tab:red", label="fall")
        axes[2, col].step(T, np.array(PS) + 0.08, where="post", c="tab:blue", label="posture")
        axes[2, col].set_yticks(range(4))
        axes[2, col].set_yticklabels([f"{a} / {b}" for a, b in zip(FALL_NAMES, POST_NAMES)], fontsize=7)
        axes[2, col].set_xlabel("t (s)")
        axes[2, col].legend(fontsize=7)
    fig.suptitle("Fail-safe fall decision (simulated; 14.6 KB int8 model)")
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "fall_events.png", dpi=105)
    print(results)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/synth_v1")
    run(ap.parse_args().model, Path(__file__).resolve().parents[1] / "docs" / "img")
