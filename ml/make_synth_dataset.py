"""Generates a SYNTHETIC set of feature windows to exercise training
before real data exists (phase F1).

Metrics obtained with it validate the chain, not the product: they are not
published. The real dataset follows docs/data-protocol.md.

Usage: python make_synth_dataset.py [--out data/synth_v1.npz] [--jobs 4]
"""
from __future__ import annotations

import argparse
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from radarref import contract as ct
from radarref.config import Room
from radarref.pipeline import Pipeline
from radarref.sim import LABELS, Person, Scene, Simulator
from radarref.split import Session, split

SUBJECTS = {f"S{i:02d}": dict(height=h, breath_hz=b, rcs=r) for i, (h, b, r) in enumerate([
    (1.58, .28, .8), (1.62, .22, .9), (1.66, .30, .9), (1.70, .25, 1.0), (1.72, .18, 1.1),
    (1.75, .33, 1.0), (1.78, .24, 1.1), (1.80, .20, 1.2), (1.84, .27, 1.2), (1.88, .23, 1.3),
    (1.64, .35, .9), (1.92, .21, 1.3)])}
ROOMS = {"R0": dict(mount_h=2.5, seed=10, clutter=[(-1.5, 1.2, .75, 4), (1.2, -1.4, .45, 3), (0, 0, 0, 2)]),
         "R1": dict(mount_h=2.6, seed=11, clutter=[(1.4, 1.3, .9, 5), (-1.0, -1.5, .5, 2), (0, 0, 0, 2)]),
         "R2": dict(mount_h=2.7, seed=12, clutter=[(-1.6, -1.2, 1.0, 6), (0, 0, 0, 2.5)]),
         "R3": dict(mount_h=2.8, seed=13, clutter=[(1.5, -1.5, .7, 4), (-1.5, 1.5, .4, 3), (0, 0, 0, 2)])}
TEST_SUBJECTS, TEST_ROOMS = ("S09", "S10", "S11"), ("R3",)
VAL_SUBJECTS, VAL_ROOMS = ("S07", "S08"), ("R2",)


def script(rng, kind: str):
    """Keyframes (t, x, y, posture, transition) and falls."""
    x, y = 1.8, rng.uniform(-.3, .3)
    keys = [(0.0, x, y, "standing")]
    t, falls = 0.0, []
    acts = list(rng.choice(["standing", "sitting", "lying_bed", "sit_fast", "pick_up"], size=3))
    if kind == "fall":
        acts = acts[:2] + ["fall"]
    for a in acts:
        nx, ny = rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4)
        dt = np.hypot(nx - x, ny - y) / rng.uniform(.6, 1.2)
        t += dt
        keys.append((t, nx, ny, "standing"))
        x, y = nx, ny
        if a == "fall":
            tr = rng.uniform(.6, 1.0)
            falls.append(t + 0.3)
            t += 0.3 + tr
            keys.append((t, x, y, "lying", tr))
            t += rng.uniform(8, 12)
            keys.append((t, x, y, "lying"))
        elif a == "pick_up":       # crouch and stand up again: the classic fall confusion
            keys.append((t + .8, x, y, "sitting", .8))
            keys.append((t + 2.0, x, y, "sitting"))
            keys.append((t + 3.0, x, y, "standing", .8))
            t += 3.0 + rng.uniform(1, 2)
            keys.append((t, x, y, "standing"))
        else:
            post = {"sit_fast": "sitting"}.get(a, a)
            tr = .5 if a == "sit_fast" else rng.uniform(1.2, 2.0)
            keys.append((t + tr, x, y, post, tr))
            t += tr + rng.uniform(5, 9)
            keys.append((t, x, y, post))
            t += 1.5
            keys.append((t, x, y, "standing", 1.5))
    return keys, falls, t + 0.1


def run_session(args):
    sid, subj, room, kind, seed = args
    rng = np.random.default_rng(seed)
    keys, falls, dur = script(rng, kind)
    person = Person(keys, fall_times=falls, **SUBJECTS[subj])
    rp = ROOMS[room]
    rm = Room(mount_h=rp["mount_h"])
    sim = Simulator(Scene(room=rm, people=[person], clutter=rp["clutter"], seed=rp["seed"] + seed))
    pipe = Pipeline(rm, sim.cfg)
    c = pipe.c
    feats, labels = [], []
    for i in range(int(dur * 10)):
        t = i / 10
        o = pipe.step(t, sim.frame(t))
        px, py, *_ = person.state(t)
        best = min(o.tracks, key=lambda tr: np.hypot(tr[2][0] - px, tr[2][1] - py), default=None)
        if best is None or np.hypot(best[2][0] - px, best[2][1] - py) > .7:
            feats.append(None)
        else:
            # the model sees exactly what travels in the record
            feats.append(ct.dequantize(c, ct.quantize(c, best[2])))
        labels.append(LABELS.index(person.label(t)))
    W, H = c.window_frames, c.window_hop_frames
    X, Y = [], []
    for e in range(W, len(feats) + 1, H):
        win = feats[e - W:e]
        if any(f is None for f in win):
            continue
        X.append(np.stack(win))
        lab = labels[e - W:e]
        Y.append(LABELS.index("fall") if LABELS.index("fall") in lab[W // 2:] else lab[-1])
    return sid, subj, room, np.array(X, np.float32).reshape(-1, W, c.n), np.array(Y, np.int8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/synth_v1.npz")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--scripts", type=int, default=3)
    a = ap.parse_args()
    allsess = [Session(f"{s}_{r}_{k}", s, r) for s in SUBJECTS for r in ROOMS for k in range(a.scripts)]
    parts = split(allsess, TEST_SUBJECTS, TEST_ROOMS, VAL_SUBJECTS, VAL_ROOMS)
    print({k: len(v) for k, v in parts.items()}, "(discarded = not simulated)")
    jobs = []
    for part in ("train", "val", "test"):
        for i, s in enumerate(parts[part]):
            kind = "fall" if int(s.id.rsplit("_", 1)[1]) % 3 != 2 else "adl"
            jobs.append((s.id, s.subject, s.room, kind, zlib.crc32(s.id.encode()) % 100000))
    with Pool(a.jobs) as pool:
        res = pool.map(run_session, jobs)
    c = ct.load()
    X = np.concatenate([r[3] for r in res])
    Y = np.concatenate([r[4] for r in res])
    sess = np.concatenate([[r[0]] * len(r[4]) for r in res])
    subj = np.concatenate([[r[1]] * len(r[4]) for r in res])
    room = np.concatenate([[r[2]] * len(r[4]) for r in res])
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, X=X, y=Y, session=sess, subject=subj, room=room,
                        contract_hash=np.uint32(c.hash32), feature_names=np.array(c.names),
                        labels=np.array(LABELS))
    print(f"{len(Y)} windows, classes {np.bincount(Y, minlength=4)} -> {out}")


if __name__ == "__main__":
    main()
