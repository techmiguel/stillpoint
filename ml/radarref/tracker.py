"""Multi-person tracking with room logic.

Decisions that answer known failures of commercial products (docs/requirements.md):
  * Occluded still person: a confirmed track is not deleted for lack of
    detections in the middle of the room. If a closer track blocks its line of
    sight it becomes OCCLUDED and is kept for up to 60 s; up to 120 s if it has
    shown breathing. Only near a door is it deleted within ~2 s.
  * Ghosts: outside the room or in an excluded zone they are dropped in the DSP;
    a new track whose radial velocity copies that of a closer one is
    multipath (mirror); a fixed source with continuous micro-Doppler and no
    breathing for 30 s is an INTERFERER (fan) and is not counted.
  * One flow for everything: there are no modes; zones, sleep and falls come
    from the same tracks.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .config import Room
from .contract import Contract

TENTATIVE, MOVING, STATIC, OCCLUDED, INTERFERER = range(5)
DT = 0.1


def _db(x: float) -> float:
    return float(10 * np.log10(x)) if x > 0 else 0.0


@dataclass
class Cluster:
    x: float
    y: float
    z: np.ndarray
    w: np.ndarray
    vr: np.ndarray
    p_lin: np.ndarray
    xy: np.ndarray

    @property
    def z_c(self):
        return float(np.average(self.z, weights=self.w))

    @property
    def vr_mean(self):
        return float(np.average(self.vr, weights=self.w))

    @property
    def vr_std(self):
        return float(np.sqrt(np.average((self.vr - self.vr_mean) ** 2, weights=self.w)))


@dataclass
class Track:
    id: int
    t0: float
    kf_x: np.ndarray
    kf_P: np.ndarray
    state: int = TENTATIVE
    confirmed: bool = False
    hits: deque = field(default_factory=lambda: deque(maxlen=20))
    last_seen: float = 0.0
    last_move: float = 0.0
    last_micro: float = -1e9
    has_breath: bool = False
    z_c: float = 1.0
    z_max: float = 1.0
    z_min: float = 1.0
    z_std: float = 0.0
    vz: float = 0.0
    xy_extent: float = 0.0
    vr_hist: deque = field(default_factory=lambda: deque(maxlen=10))
    anchor: tuple = (0.0, 0.0)
    anchor_t: float = 0.0
    spread_ema: float = 0.0
    breath_hz: float = 0.0
    breath_snr: float = 0.0
    micro_db: float = 0.0
    last_cluster: Cluster | None = None
    occluded: bool = False

    @property
    def x(self):
        return float(self.kf_x[0])

    @property
    def y(self):
        return float(self.kf_x[1])


class Tracker:
    GATE = 0.8
    HOLD = {"tentative": 0.5, "exit": 2.0, "occluded": 60.0, "breath": 120.0, "default": 30.0}
    MICRO_WINDOW_S = 10.0
    INTERFERER_S = 20.0

    def __init__(self, room: Room, contract: Contract):
        self.room, self.c = room, contract
        self.tracks: list[Track] = []
        self.motion_hist: deque = deque()
        self.next_id = 1
        self.micro_cand: list[list] = []      # [x, y, n, t]
        self.proposed_exclusions: list = []
        F = np.eye(4)
        F[0, 2] = F[1, 3] = DT
        self.F = F
        q = 0.5
        G = np.array([[DT ** 2 / 2, 0], [0, DT ** 2 / 2], [DT, 0], [0, DT]])
        self.Q = G @ G.T * q ** 2
        self.H = np.eye(2, 4)
        self.sensor = np.array([0.0, 0.0, room.mount_h])

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def cluster(dets, radius: float = 0.6) -> list[Cluster]:
        dets = sorted(dets, key=lambda d: -d.power_db)
        groups: list[list] = []
        for d in dets:
            for g in groups:
                if np.hypot(d.x - g[0].x, d.y - g[0].y) < radius:
                    g.append(d)
                    break
            else:
                groups.append([d])
        out = []
        for g in groups:
            p = np.array([10 ** (d.power_db / 10) for d in g])
            w = p / p.sum()
            xy = np.array([[d.x, d.y] for d in g])
            out.append(Cluster(float(w @ xy[:, 0]), float(w @ xy[:, 1]),
                               np.array([d.z for d in g]), w, np.array([d.vr for d in g]), p, xy))
        return out

    def _kf_update(self, tr: Track, zx: float, zy: float, r: float):
        R = np.eye(2) * r ** 2
        S = self.H @ tr.kf_P @ self.H.T + R
        K = tr.kf_P @ self.H.T @ np.linalg.inv(S)
        tr.kf_x = tr.kf_x + K @ (np.array([zx, zy]) - self.H @ tr.kf_x)
        tr.kf_P = (np.eye(4) - K @ self.H) @ tr.kf_P

    def _new_track(self, t, x, y) -> Track:
        tr = Track(self.next_id, t, np.array([x, y, 0.0, 0.0]), np.diag([0.1, 0.1, 1.0, 1.0]),
                   last_seen=t, last_move=t, anchor=(x, y), anchor_t=t)
        self.next_id = self.next_id % 250 + 1
        self.tracks.append(tr)
        return tr

    def _range(self, tr: Track) -> float:
        return float(np.linalg.norm(np.array([tr.x, tr.y, tr.z_c]) - self.sensor))

    def _is_occluded(self, tr: Track) -> bool:
        u = np.array([tr.x, tr.y, tr.z_c]) - self.sensor
        ru = np.linalg.norm(u)
        for o in self.tracks:
            if o is tr or not o.confirmed or o.state == INTERFERER:
                continue
            v = np.array([o.x, o.y, o.z_max]) - self.sensor
            rv = np.linalg.norm(v)
            if rv < ru - 0.3 and np.linalg.norm(np.cross(u / ru, v / rv)) < 0.35:
                return True
        return False

    def _is_multipath(self, tr: Track) -> bool:
        if len(tr.vr_hist) < 8:
            return False
        a = np.array(tr.vr_hist)
        for o in self.tracks:
            if o is tr or not o.confirmed or len(o.vr_hist) < 8:
                continue
            n = min(len(a), len(o.vr_hist))
            a, b = np.array(tr.vr_hist)[-n:], np.array(o.vr_hist)[-n:]
            if (np.std(a) > 0.05 and np.std(b) > 0.05 and np.corrcoef(a, b)[0, 1] > 0.9
                    and self._range(tr) > self._range(o) + 0.3):
                return True
        return False

    # -- per-frame step ----------------------------------------------------
    def step(self, t: float, dets) -> list[Track]:
        moves = [d for d in dets if d.kind == "move"]
        micros = [d for d in dets if d.kind == "micro"]
        clusters = self.cluster(moves)

        for tr in self.tracks:
            tr.kf_x = self.F @ tr.kf_x
            tr.kf_P = self.F @ tr.kf_P @ self.F.T + self.Q
            tr.last_cluster = None

        # greedy association by horizontal distance; a still track does not
        # take a measurement from someone walking quickly past it (avoids
        # identity swaps when people cross)
        def cost(c, tr):
            d = np.hypot(c.x - tr.x, c.y - tr.y)
            if tr.state in (STATIC, OCCLUDED) and abs(c.vr_mean) > 0.3:
                d += 0.5
            return d
        pairs = sorted(((cost(c, tr), i, j)
                        for i, c in enumerate(clusters) for j, tr in enumerate(self.tracks)))
        used_c, used_t = set(), set()
        for d, i, j in pairs:
            if d > self.GATE or i in used_c or j in used_t:
                continue
            used_c.add(i)
            used_t.add(j)
            self._update_move(self.tracks[j], clusters[i], t)
        for i, c in enumerate(clusters):
            if i not in used_c:
                self._update_move(self._new_track(t, c.x, c.y), c, t)

        # The micro-motion window (10 s) holds the trail of whoever moved: a
        # micro detection where there was recent macro motion is not
        # breathing and is ignored.
        for c in clusters:
            self.motion_hist.append((t, c.x, c.y))
        while self.motion_hist and t - self.motion_hist[0][0] > self.MICRO_WINDOW_S:
            self.motion_hist.popleft()
        for m in micros:
            if not any(np.hypot(m.x - x, m.y - y) < 0.6 for _, x, y in self.motion_hist):
                self._update_micro(t, m)

        self._update_states(t, used_t)
        return [tr for tr in self.tracks if tr.confirmed]

    def _update_move(self, tr: Track, c: Cluster, t: float):
        self._kf_update(tr, c.x, c.y, 0.15)
        tr.last_cluster = c
        tr.last_seen = t
        tr.hits.append(1)
        zc = c.z_c
        resid = zc - tr.z_c
        tr.z_c += 0.5 * resid
        tr.vz = 0.8 * tr.vz + 0.2 * resid / DT
        tr.z_max = 0.6 * tr.z_max + 0.4 * float(c.z.max())
        tr.z_min = 0.6 * tr.z_min + 0.4 * float(c.z.min())
        tr.z_std = 0.6 * tr.z_std + 0.4 * float(np.sqrt(np.average((c.z - zc) ** 2, weights=c.w)))
        if len(c.xy) > 1:
            cov = np.cov(c.xy.T, aweights=c.w + 1e-9)
            tr.xy_extent = 0.7 * tr.xy_extent + 0.3 * float(np.sqrt(max(np.linalg.eigvalsh(cov)[-1], 0)))
        tr.vr_hist.append(c.vr_mean)
        tr.spread_ema = 0.95 * tr.spread_ema + 0.05 * c.vr_std
        speed = float(np.hypot(tr.kf_x[2], tr.kf_x[3]))
        if speed > 0.3 or abs(c.vr_mean) > 0.3 or c.vr_std > 0.3:
            tr.last_move = t
        if not tr.confirmed and sum(list(tr.hits)[-5:]) >= 3:
            if self._is_multipath(tr):
                tr.last_seen = -1e9          # dropped in _update_states
            else:
                tr.confirmed = True

    def _update_micro(self, t: float, m):
        best, bd = None, 0.7
        for tr in self.tracks:
            d = np.hypot(m.x - tr.x, m.y - tr.y)
            if d < bd and tr.state != INTERFERER:
                best, bd = tr, d
        breath_ok = 0.12 <= m.breath_hz <= 0.6 and m.breath_snr_db > 15
        if best is not None:
            self._kf_update(best, m.x, m.y, 0.35)
            best.last_seen = t
            best.last_micro = t
            best.micro_db, best.breath_hz, best.breath_snr = m.micro_db, m.breath_hz, m.breath_snr_db
            best.has_breath |= breath_ok and best.confirmed
            if best.last_cluster is None:     # still: the height comes from the chest
                best.z_c += 0.3 * (m.z - best.z_c)
                best.z_max += 0.3 * (m.z + 0.15 - best.z_max)
                best.z_min += 0.3 * (m.z - 0.15 - best.z_min)
            return
        if not breath_ok:
            return
        for c in self.micro_cand:
            if np.hypot(m.x - c[0], m.y - c[1]) < 0.5 and t - c[3] < 1.5:
                c[0], c[1], c[2], c[3] = 0.5 * (c[0] + m.x), 0.5 * (c[1] + m.y), c[2] + 1, t
                if c[2] >= 3:   # still person present since start-up
                    tr = self._new_track(t, c[0], c[1])
                    tr.confirmed, tr.has_breath, tr.state = True, True, STATIC
                    tr.z_c, tr.z_max, tr.z_min = m.z, m.z + .15, m.z - .15
                    tr.last_micro = t
                    self.micro_cand.remove(c)
                return
        self.micro_cand.append([m.x, m.y, 1, t])

    def _update_states(self, t: float, updated: set):  # noqa: ARG002 (updated: reserved)
        self.micro_cand = [c for c in self.micro_cand if t - c[3] < 1.5]
        keep = []
        for j, tr in enumerate(self.tracks):
            if tr.last_cluster is None:
                # recent breathing is also evidence of presence
                tr.hits.append(1 if t - tr.last_micro < 1.0 else 0)
                # a person without measurements does not keep moving: the
                # extrapolation is damped so the track does not drift to a door
                tr.kf_x[2:] *= 0.7
                tr.vz *= 0.7
            if not self.room.inside(tr.x, tr.y, margin=0.3):
                continue                      # left through a wall: no longer in the room
            tr.occluded = False
            if tr.state == INTERFERER:
                pass
            elif tr.last_cluster is not None and t - tr.last_move < 1.0:
                tr.state = MOVING if tr.confirmed else TENTATIVE
            elif t - tr.last_micro < 3.0:
                tr.state = STATIC
            elif tr.confirmed and self._is_occluded(tr):
                tr.state, tr.occluded = OCCLUDED, True
            elif tr.confirmed:
                tr.state = STATIC if tr.has_breath else tr.state
            # fixed source with continuous micro-Doppler and no breathing = interferer
            if np.hypot(tr.x - tr.anchor[0], tr.y - tr.anchor[1]) > 0.4:
                tr.anchor, tr.anchor_t = (tr.x, tr.y), t
            elif (tr.confirmed and not tr.has_breath and t - tr.anchor_t > self.INTERFERER_S
                  and tr.spread_ema > 0.5 and sum(tr.hits) >= 16 and tr.state != INTERFERER):
                tr.state = INTERFERER
                self.proposed_exclusions.append((tr.x - .4, tr.x + .4, tr.y - .4, tr.y + .4))
            miss = t - tr.last_seen
            if not tr.confirmed:
                hold = self.HOLD["tentative"]
            elif self.room.near_exit(tr.x, tr.y):
                hold = self.HOLD["exit"]
            elif tr.state == OCCLUDED:
                hold = self.HOLD["occluded"]
            elif tr.has_breath:
                hold = self.HOLD["breath"]
            else:
                hold = self.HOLD["default"]
            if miss <= hold:
                keep.append(tr)
        self.tracks = keep

    # -- output ------------------------------------------------------------
    def count(self) -> int:
        return sum(1 for tr in self.tracks if tr.confirmed and tr.state != INTERFERER)

    def features(self, tr: Track, t: float) -> np.ndarray:
        c = tr.last_cluster
        f = np.zeros(self.c.n)
        ix = self.c.index
        f[ix("x")], f[ix("y")] = tr.x, tr.y
        f[ix("z_centroid")], f[ix("z_max")], f[ix("z_min")], f[ix("z_std")] = tr.z_c, tr.z_max, tr.z_min, tr.z_std
        f[ix("xy_extent")] = tr.xy_extent
        f[ix("vx")], f[ix("vy")], f[ix("vz")] = tr.kf_x[2], tr.kf_x[3], tr.vz
        if c is not None:
            f[ix("vr_mean")], f[ix("vr_std")] = c.vr_mean, c.vr_std
            f[ix("e_approach_db")] = _db(c.p_lin[c.vr < 0].sum())
            f[ix("e_recede_db")] = _db(c.p_lin[c.vr > 0].sum())
            f[ix("n_points")] = len(c.z)
            f[ix("power_db")] = _db(c.p_lin.sum())
        f[ix("micro_db")] = tr.micro_db if t - tr.last_micro < 3 else 0.0
        f[ix("breath_hz")] = tr.breath_hz if t - tr.last_micro < 3 else 0.0
        f[ix("breath_snr_db")] = tr.breath_snr if t - tr.last_micro < 3 else 0.0
        f[ix("range")] = self._range(tr)
        f[ix("state")] = tr.state
        f[ix("still_s")] = min(t - tr.last_move, 3276.0)
        f[ix("occluded")] = float(tr.occluded)
        f[ix("quality")] = sum(tr.hits) / max(len(tr.hits), 1)
        return f
