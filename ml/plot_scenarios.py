"""Draws the progress figures of the canonical scenarios into docs/img/.

Usage: python plot_scenarios.py [name ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from radarref import scenarios  # noqa: E402
from radarref.pipeline import Pipeline  # noqa: E402
from radarref.sim import Simulator  # noqa: E402
from radarref.tracker import INTERFERER, OCCLUDED, STATIC  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
STATE_NAME = {0: "tentative", 1: "moving", 2: "static", 3: "occluded", 4: "interferer"}


def run(name: str) -> Path:
    scene, dur, truth = scenarios.ALL[name]()
    sim = Simulator(scene)
    p = Pipeline(scene.room, sim.cfg)
    ts, counts, pts = [], [], []
    rd_snap = None
    for i in range(int(dur * 10)):
        t = i / 10
        adc = sim.frame(t)
        o = p.step(t, adc)
        ts.append(t)
        counts.append(o.count)
        for tid, st, f in o.tracks:
            pts.append((t, tid, st, f[0], f[1], f[2]))
        if rd_snap is None and o.tracks and t > 3:
            X = np.fft.rfft(adc * np.hanning(adc.shape[-1]), axis=-1)[..., :sim.cfg.n_range]
            X = X - X.mean(axis=1, keepdims=True)
            rd_snap = (np.abs(np.fft.fftshift(np.fft.fft(X, axis=1), axes=1)) ** 2).sum(0), t
    pts = np.array(pts) if pts else np.zeros((0, 6))
    room = scene.room

    fig = plt.figure(figsize=(13, 4.6))
    fig.suptitle(f"Scenario \"{name}\" (simulated) - reference chain", fontsize=12)
    ax = fig.add_subplot(1, 3, 1)
    ax.add_patch(plt.Rectangle((room.x_min, room.y_min), room.x_max - room.x_min,
                               room.y_max - room.y_min, fill=False, lw=1.5))
    for b in room.exits:
        ax.add_patch(plt.Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], color="tab:green", alpha=.25))
    tt = np.arange(0, dur, 0.1)
    for k, per in enumerate(scene.people):
        xy = np.array([per.state(t)[:2] for t in tt])
        ax.plot(xy[:, 0], xy[:, 1], "k--", lw=1, label="truth" if k == 0 else None)
    for tid in np.unique(pts[:, 1]) if len(pts) else []:
        m = pts[:, 1] == tid
        ax.plot(pts[m, 3], pts[m, 4], ".", ms=3, label=f"track {int(tid)}")
    occ = pts[pts[:, 2] == OCCLUDED] if len(pts) else pts
    if len(occ):
        ax.plot(occ[:, 3], occ[:, 4], "x", color="tab:red", ms=6, label="occluded (kept)")
    itf = pts[pts[:, 2] == INTERFERER] if len(pts) else pts
    if len(itf):
        ax.plot(itf[:, 3], itf[:, 4], "s", mfc="none", color="tab:purple", ms=8, label="interferer (not counted)")
    ax.plot(0, 0, "^", color="k", ms=9, label="sensor (ceiling)")
    ax.set_xlim(room.x_min - .6, room.x_max + .9)
    ax.set_ylim(room.y_min - .6, room.y_max + .6)
    ax.set_aspect("equal")
    ax.set_title("Top view: truth vs. tracks")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.legend(fontsize=7, loc="lower left")

    ax = fig.add_subplot(1, 3, 2)
    ax.step(ts, [truth(t) for t in ts], "k--", where="post", label="truth")
    ax.step(ts, counts, where="post", color="tab:blue", label="sensor")
    if len(pts):
        for tid in np.unique(pts[:, 1]):
            m = pts[:, 1] == tid
            ax.scatter(pts[m, 0], np.full(m.sum(), -0.4 - 0.15 * (tid % 4)), c=pts[m, 2], cmap="tab10",
                       vmin=0, vmax=9, s=4)
    ax.set_ylim(-1.2, 3.5)
    ax.set_title("People in the room (dots: state of each track)")
    ax.set_xlabel("t (s)")
    ax.legend(fontsize=8)

    ax = fig.add_subplot(1, 3, 3)
    if rd_snap is not None:
        rd, t_s = rd_snap
        cfg = sim.cfg
        ext = [0, cfg.n_range * cfg.range_res, -cfg.v_max, cfg.v_max]
        ax.imshow(10 * np.log10(rd + 1e-12), aspect="auto", origin="lower", extent=ext, cmap="magma",
                  vmin=10 * np.log10(np.median(rd)) , vmax=10 * np.log10(rd.max()))
        ax.set_title(f"Range-Doppler map (t = {t_s:.1f} s, MTI)")
        ax.set_xlabel("range (m)")
        ax.set_ylabel("radial velocity (m/s)")
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"scenario_{name}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    err = np.mean(np.array(counts) != np.array([truth(t) for t in ts]))
    print(f"{name}: frames with a wrong count {100 * err:.1f} % -> {path}")
    return path


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(scenarios.ALL)):
        run(n)
