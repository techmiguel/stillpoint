"""FMCW simulator of indoor scenes for development and regression tests.

It does not replace real data: it exercises the full chain (IF signal
-> DSP -> tracking -> features -> classifier) and pins test cases for the
known problems (occluded still person, fan, mirror) before the kit is
available. No metric obtained here is ever published.

Model: each person is a set of point scatterers whose geometry depends on
the posture; the chest moves with breathing. The IF signal of each RX is
a sum of real cosines (the BGT60TR13C delivers real samples).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import C0, RadarConfig, Room

# Scatterers per posture: (offset along the heading [m], height [m], RCS weight, is_chest)
POSTURES = {
    "standing": [(0.00, 1.65, .5, 0), (0.00, 1.30, 1., 1), (0.00, 0.95, .8, 0),
                 (0.05, 0.50, .5, 0), (0.05, 0.10, .3, 0)],
    "sitting":  [(0.00, 1.25, .5, 0), (0.00, 0.95, 1., 1), (0.10, 0.50, .8, 0),
                 (0.45, 0.50, .5, 0), (0.50, 0.10, .3, 0)],
    "lying":    [(-0.80, 0.15, .5, 0), (-0.40, 0.22, 1., 1), (0.00, 0.18, .8, 0),
                 (0.45, 0.12, .5, 0), (0.80, 0.10, .3, 0)],
    "lying_bed": [(-0.80, 0.65, .5, 0), (-0.40, 0.72, 1., 1), (0.00, 0.68, .8, 0),
                  (0.45, 0.62, .5, 0), (0.80, 0.60, .3, 0)],
}
LABELS = ("standing", "sitting", "lying", "fall")


@dataclass
class Person:
    """Keyframe trajectory: (t, x, y, posture). Linear interpolation.

    `transition_s` sets how fast the posture changes; a fall is a
    standing->lying change with transition_s ~0.6-1.0 s.
    """
    keys: list
    height: float = 1.75
    breath_hz: float = 0.25
    breath_amp: float = 0.003
    rcs: float = 1.0
    transition_s: float = 1.5
    fall_times: list = field(default_factory=list)  # fall start times (label)

    def state(self, t: float):
        ks = self.keys
        if t <= ks[0][0]:
            k0 = k1 = ks[0]
        elif t >= ks[-1][0]:
            k0 = k1 = ks[-1]
        else:
            i = max(j for j in range(len(ks)) if ks[j][0] <= t)
            k0, k1 = ks[i], ks[min(i + 1, len(ks) - 1)]
        span = max(k1[0] - k0[0], 1e-9)
        a = np.clip((t - k0[0]) / span, 0, 1)
        x = k0[1] + a * (k1[1] - k0[1])
        y = k0[2] + a * (k1[2] - k0[2])
        heading = np.arctan2(k1[2] - k0[2], k1[1] - k0[1]) if k1 is not k0 else 0.0
        # posture: changes at the end of the segment, over `transition_s`
        tp = k1[0] - t
        trans = k1[4] if len(k1) > 4 else self.transition_s   # segment-specific duration
        if k0[3] == k1[3] or tp > trans:
            pa, pb, b = k0[3], k0[3], 0.0
        else:
            pa, pb, b = k0[3], k1[3], 1 - tp / trans
        moving = np.hypot(k1[1] - k0[1], k1[2] - k0[2]) > 1e-3 and k1 is not k0
        speed = np.hypot(k1[1] - k0[1], k1[2] - k0[2]) / span if moving else 0.0
        return x, y, heading, pa, pb, b, speed

    def label(self, t: float) -> str:
        if any(ft <= t < ft + 3.0 for ft in self.fall_times):
            return "fall"
        x, y, h, pa, pb, b, _ = self.state(t)
        p = pb if b > 0.5 else pa
        return "lying" if p.startswith("lying") else p

    def scatterers(self, t: np.ndarray):
        """Positions (len(t), n, 3), weights (n,), chest mask (n,)."""
        s = self.height / 1.75
        out = []
        for tt in np.atleast_1d(t):
            x, y, h, pa, pb, b, speed = self.state(float(tt))
            A, B = np.array(POSTURES[pa]), np.array(POSTURES[pb])
            g = (1 - b) * A + b * B
            ch, sh = np.cos(h), np.sin(h)
            pts = np.stack([x + g[:, 0] * ch, y + g[:, 0] * sh, g[:, 1] * s], axis=1)
            if speed > 0.05:  # leg swing while walking (micro-Doppler)
                sw = 0.15 * np.sin(2 * np.pi * 1.8 * tt) * np.array([0, 0, 0, 1, -1])
                pts[:, 0] += sw * ch
                pts[:, 1] += sw * sh
            chest = g[:, 3] > 0
            pts[chest, 2] += self.breath_amp * np.sin(2 * np.pi * self.breath_hz * tt)
            out.append(pts)
        g0 = np.array(POSTURES["standing"])
        return np.array(out), g0[:, 2] * self.rcs, g0[:, 3] > 0


@dataclass
class Fan:
    """Standing fan: 3 blades spinning in a vertical plane (a ghost source)."""
    x: float
    y: float
    z: float = 1.1
    radius: float = 0.18
    rps: float = 4.0
    rcs: float = 0.6

    def scatterers(self, t: np.ndarray):
        t = np.atleast_1d(t)[:, None]
        ang = 2 * np.pi * self.rps * t + np.array([0, 2.094, 4.189])[None, :]
        pts = np.stack([np.full_like(ang, self.x) + self.radius * np.cos(ang),
                        np.full_like(ang, self.y),
                        self.z + self.radius * np.sin(ang)], axis=2)
        return pts, np.full(3, self.rcs / 3), np.zeros(3, bool)


@dataclass
class Scene:
    room: Room = field(default_factory=Room)
    people: list = field(default_factory=list)
    fans: list = field(default_factory=list)
    clutter: list = field(default_factory=lambda: [(-1.5, 1.2, 0.75, 4.0), (1.2, -1.4, 0.45, 3.0),
                                                   (0.0, 0.0, 0.0, 2.0)])
    mirror_wall_x: float | None = None   # specular wall: mirror image of the people
    noise_std: float = 2e-3
    seed: int = 0


class Simulator:
    def __init__(self, scene: Scene, cfg: RadarConfig = RadarConfig()):
        cfg.check_eu()
        self.s, self.cfg = scene, cfg
        self.rng = np.random.default_rng(scene.seed)
        self.sensor = np.array([0.0, 0.0, scene.room.mount_h])
        self.rx = np.array([[p[0], p[1], 0.0] for p in cfg.rx_positions()])
        self.n = np.arange(cfg.n_samples)
        self.win = np.hanning(cfg.n_samples)

    def _gather(self, tc: np.ndarray):
        pts, w = [], []
        people = []
        for p in self.s.people:
            P, W, _ = p.scatterers(tc)
            people.append((P, W))
        # shadowing: another person closer and in the line of sight attenuates
        for i, (P, W) in enumerate(people):
            att = np.ones(P.shape[1])
            for j, (Q, _) in enumerate(people):
                if i == j:
                    continue
                for k in range(P.shape[1]):
                    u = P[0, k] - self.sensor
                    r = np.linalg.norm(u)
                    for q in Q[0]:
                        v = q - self.sensor
                        rv = np.linalg.norm(v)
                        if rv < r - 0.3 and np.linalg.norm(np.cross(u / r, v)) < 0.35:
                            att[k] = 0.15
            pts.append(P)
            w.append(W * att)
            if self.s.mirror_wall_x is not None:  # mirror image (double path)
                M = P.copy()
                M[..., 0] = 2 * self.s.mirror_wall_x - M[..., 0]
                pts.append(M)
                w.append(W * att * 0.35)
        for f in self.s.fans:
            P, W, _ = f.scatterers(tc)
            pts.append(P)
            w.append(W)
        for (x, y, z, rcs) in self.s.clutter:
            pts.append(np.tile([[x, y, z]], (len(tc), 1, 1)))
            w.append(np.array([rcs]))
        return np.concatenate(pts, axis=1), np.concatenate(w)

    def frame(self, t0: float) -> np.ndarray:
        """ADC samples (n_rx, n_chirps, n_samples), real, normalized 12 bits."""
        cfg = self.cfg
        tc = t0 + np.arange(cfg.n_chirps) * cfg.t_chirp_s
        P, W = self._gather(tc)                          # (M, K, 3), (K,)
        d = P - self.sensor                             # (M, K, 3)
        R = np.linalg.norm(d, axis=2)                   # (M, K)
        u = d / R[..., None]
        gain = np.clip(-u[..., 2], 0, 1) ** 1.5         # approx. cos^1.5 pattern towards the floor
        amp = 0.15 * np.sqrt(W)[None, :] * gain / np.maximum(R, 0.3) ** 2
        f_if = 2 * cfg.slope * R / C0                   # (M, K)
        ph_r = 4 * np.pi * cfg.f_start_hz * R / C0
        out = np.empty((cfg.n_rx, cfg.n_chirps, cfg.n_samples))
        for k in range(cfg.n_rx):
            ph = ph_r + 2 * np.pi * (u[..., :2] @ self.rx[k, :2]) / cfg.wavelength
            arg = 2 * np.pi * f_if[..., None] * self.n / cfg.fs_hz + ph[..., None]
            out[k] = np.einsum("mk,mkn->mn", amp, np.cos(arg))
        out += self.rng.normal(0, self.s.noise_std, out.shape)
        return np.round(np.clip(out, -1, 1) * 2047) / 2047

    def labels(self, t: float):
        return [p.label(t) for p in self.s.people]

    def truth(self, t: float):
        out = []
        for p in self.s.people:
            x, y, *_ = p.state(t)
            out.append((x, y))
        return out
