"""Full reference chain: ADC samples -> tracks -> contract records."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import contract as ct
from .config import RadarConfig, Room
from .dsp import FrontEnd
from .tracker import Tracker


@dataclass
class FrameOut:
    t: float
    count: int
    tracks: list = field(default_factory=list)   # [(track_id, state, features)]


class Pipeline:
    def __init__(self, room: Room, cfg: RadarConfig = RadarConfig(), contract: ct.Contract | None = None):
        cfg.check_eu()
        self.c = contract or ct.load()
        if abs(self.c.frame_rate_hz - cfg.frame_rate_hz) > 1e-9:
            raise ValueError("frame rate does not match the contract")
        self.fe = FrontEnd(cfg, room)
        self.tr = Tracker(room, self.c)
        self.frame_id = 0

    def step(self, t: float, adc: np.ndarray) -> FrameOut:
        dets = self.fe.process(adc)
        tracks = self.tr.step(t, dets)
        out = FrameOut(t, self.tr.count())
        for trk in tracks:
            out.tracks.append((trk.id, trk.state, self.tr.features(trk, t)))
        self.frame_id += 1
        return out

    def records(self, out: FrameOut) -> list[bytes]:
        return [ct.pack(self.c, self.frame_id, int(out.t * 1000), tid, 0, f)
                for tid, _, f in out.tracks]


def run_scene(sim, duration_s: float, room: Room | None = None):
    """Runs a simulator and returns the list of FrameOut."""
    p = Pipeline(room or sim.s.room, sim.cfg)
    n = int(round(duration_s * sim.cfg.frame_rate_hz))
    return [p.step(i / sim.cfg.frame_rate_hz, sim.frame(i / sim.cfg.frame_rate_hz)) for i in range(n)]
