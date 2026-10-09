"""Radar and installation parameters for v1.

Emission values are bounded to the European 57-64 GHz band
(see docs/regulatory.md). `RadarConfig.check_eu()` runs in the
tests and its C counterpart blocks out-of-range configurations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

C0 = 299_792_458.0


@dataclass(frozen=True)
class RadarConfig:
    f_start_hz: float = 60.0e9
    bandwidth_hz: float = 1.25e9        # 12 cm resolution
    n_samples: int = 128                # real samples per chirp -> 64 useful bins
    fs_hz: float = 2.0e6                # active ramp = 64 us
    n_chirps: int = 32
    t_chirp_s: float = 350e-6           # chirp repetition -> vmax 3.5 m/s
    frame_rate_hz: float = 10.0
    n_rx: int = 3
    eirp_dbm: float = 10.0              # configuration target, far below the limit

    # EU limits used by the check (see docs/regulatory.md).
    EU_F_MIN: float = 57.0e9
    EU_F_MAX: float = 64.0e9
    EU_EIRP_MAX_DBM: float = 20.0

    @property
    def f_center_hz(self) -> float:
        return self.f_start_hz + self.bandwidth_hz / 2

    @property
    def wavelength(self) -> float:
        return C0 / self.f_center_hz

    @property
    def ramp_s(self) -> float:
        return self.n_samples / self.fs_hz

    @property
    def slope(self) -> float:
        return self.bandwidth_hz / self.ramp_s

    @property
    def range_res(self) -> float:
        return C0 / (2 * self.bandwidth_hz)

    @property
    def n_range(self) -> int:
        return self.n_samples // 2

    @property
    def v_max(self) -> float:
        return self.wavelength / (4 * self.t_chirp_s)

    @property
    def v_res(self) -> float:
        return self.wavelength / (2 * self.n_chirps * self.t_chirp_s)

    @property
    def duty(self) -> float:
        return self.n_chirps * self.t_chirp_s * self.frame_rate_hz

    def rx_positions(self):
        """L-shaped antennas at lambda/2 (sensor: x, y in the board plane)."""
        d = self.wavelength / 2
        return [(0.0, 0.0), (d, 0.0), (0.0, d)]

    def check_eu(self) -> None:
        f_end = self.f_start_hz + self.bandwidth_hz
        if self.f_start_hz < self.EU_F_MIN or f_end > self.EU_F_MAX:
            raise ValueError("sweep outside 57-64 GHz")
        if self.eirp_dbm > self.EU_EIRP_MAX_DBM:
            raise ValueError("EIRP above 20 dBm (100 mW)")
        if self.duty >= 1.0:
            raise ValueError("chirps do not fit in the frame")


@dataclass
class Room:
    """v1 installation: a single mounting type, ceiling, antennas facing the floor."""
    mount_h: float = 2.6
    x_min: float = -2.0
    x_max: float = 2.0
    y_min: float = -2.0
    y_max: float = 2.0
    # exit zones (doors): (xmin, xmax, ymin, ymax)
    exits: list = field(default_factory=lambda: [(1.6, 2.0, -0.5, 0.5)])
    # zones excluded by the user (fan, curtain...)
    exclusions: list = field(default_factory=list)

    def inside(self, x: float, y: float, margin: float = 0.15) -> bool:
        return (self.x_min - margin <= x <= self.x_max + margin and
                self.y_min - margin <= y <= self.y_max + margin)

    @staticmethod
    def _in(box, x, y) -> bool:
        return box[0] <= x <= box[1] and box[2] <= y <= box[3]

    def near_exit(self, x: float, y: float) -> bool:
        return any(self._in((b[0] - .3, b[1] + .3, b[2] - .3, b[3] + .3), x, y) for b in self.exits)

    def excluded(self, x: float, y: float) -> bool:
        return any(self._in(b, x, y) for b in self.exclusions)
