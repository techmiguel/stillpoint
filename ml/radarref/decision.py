"""Per-track fail-safe decision. Exact mirror: firmware/src/decision.c.

Principle: without confidence the output is "uncertain"; a posture is never
invented and a possible fall is never silenced. A fall is a notification, not a
safety device (docs/requirements.md).

Published posture: 0 uncertain, 1 standing, 2 sitting, 3 lying.
Fall:  0 none, 1 suspected, 2 confirmed, 3 uncertain (possible fall that
       cannot be verified: track occluded or lost while suspected).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

P_UNCERTAIN, P_STANDING, P_SITTING, P_LYING = range(4)
F_NONE, F_SUSPECTED, F_CONFIRMED, F_UNCERTAIN = range(4)


@dataclass(frozen=True)
class Params:
    p_min: float = 0.60        # minimum confidence to publish a posture
    p_fall: float = 0.50       # fall probability that opens a suspicion
    vz_fall: float = -0.80     # m/s, fast descent (independent physical rule)
    z_floor: float = 0.55      # m, centroid "on the floor" (bed ~0.6-0.8: risk R6)
    z_up: float = 1.00         # m, centroid "up"
    confirm_s: float = 4.0     # time on the floor and still before confirming
    still_s: float = 2.0
    resolve_max_s: float = 15.0
    clear_s: float = 5.0       # time up before a confirmed fall is cleared
    q_min: float = 0.30        # minimum track quality
    ood_max: int = 3           # max. number of out-of-range features


@dataclass(frozen=True)
class Inputs:
    """What the firmware has at each evaluation (2 Hz) for one track."""
    t: float
    probs: tuple              # (standing, sitting, lying, fall)
    z_c: float
    vz_min: float             # minimum vz over the window
    still_s: float
    quality: float
    occluded: bool
    ood_count: int


class TrackDecision:
    def __init__(self, p: Params = Params()):
        self.p = p
        self.fall = F_NONE
        self.t_susp = 0          # ms
        self.t_up = None         # ms

    def update(self, x: Inputs):
        p = self.p
        probs = np.asarray(x.probs, dtype=np.float64)
        # Posture needs recent evidence. A fall does not: someone lying still
        # after a fall stops producing detections, and that must not prevent
        # confirming it. The track only has to exist and not be occluded.
        trusted_fall = not x.occluded and x.ood_count <= p.ood_max
        trusted = trusted_fall and x.quality >= p.q_min

        # --- posture -------------------------------------------------------
        k = int(np.argmax(probs[:3]))
        conf = float(probs[k] / max(probs[:3].sum(), 1e-6))
        posture = (k + 1) if (trusted and conf >= p.p_min) else P_UNCERTAIN

        # --- fall ----------------------------------------------------------
        # Times are compared in whole milliseconds: an alarm must not depend
        # on floating-point rounding (with float, 9.4 - 5.4 < 4).
        tm = int(round(x.t * 1000))
        ms = lambda s: int(round(s * 1000))  # noqa: E731
        trigger = probs[3] >= p.p_fall or (x.vz_min <= p.vz_fall and x.z_c < p.z_floor)
        if self.fall == F_NONE:
            if trigger and trusted_fall:
                self.fall, self.t_susp = F_SUSPECTED, tm
        elif self.fall == F_SUSPECTED:
            if not trusted_fall:
                self.fall = F_UNCERTAIN
            elif x.z_c > p.z_up:
                self.fall = F_NONE                      # got up / false alarm
            elif (tm - self.t_susp >= ms(p.confirm_s) and x.z_c < p.z_floor
                  and x.still_s >= p.still_s):
                self.fall, self.t_up = F_CONFIRMED, None
            elif tm - self.t_susp >= ms(p.resolve_max_s):
                self.fall = F_UNCERTAIN                 # unresolved: reported as uncertain
        elif self.fall in (F_CONFIRMED, F_UNCERTAIN):
            if trusted_fall and x.z_c > p.z_up:
                self.t_up = tm if self.t_up is None else self.t_up
                if tm - self.t_up >= ms(p.clear_s):
                    self.fall, self.t_up = F_NONE, None
            else:
                self.t_up = None
                if self.fall == F_UNCERTAIN and trusted_fall and x.z_c < p.z_floor and x.still_s >= p.still_s:
                    self.fall = F_CONFIRMED
        return posture, conf, self.fall


def inputs_from_window(c, win: np.ndarray, t: float, probs, lo=None, hi=None, used=None) -> Inputs:
    """Builds Inputs from a (W, n) window in physical units."""
    last = win[-1]
    ood = 0
    if lo is not None:
        idx = used if used is not None else np.arange(c.n)
        ood = int(np.sum((last[idx] < lo) | (last[idx] > hi)))
    return Inputs(t=t, probs=tuple(float(v) for v in probs), z_c=float(last[c.index("z_centroid")]),
                  vz_min=float(win[:, c.index("vz")].min()), still_s=float(last[c.index("still_s")]),
                  quality=float(last[c.index("quality")]), occluded=bool(last[c.index("occluded")] > .5),
                  ood_count=ood)
