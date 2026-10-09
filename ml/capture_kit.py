"""Frame capture with the BGT60TR13C evaluation kit (phase F1).

Uses the Infineon radar SDK (Python package `ifxradarsdk`, installed with the
SDK itself). Writes an .rfad file (the same format used by the Python reference
and the firmware replayer) and a .json with the session metadata.

  python capture_kit.py --session S03_R1_a --subject S03 --room R1 --seconds 300
  python capture_kit.py --simulated --seconds 20          # no kit: simulated device
  python capture_kit.py ... --live                          # process and print the count on the fly

Before transmitting, the sweep and power are checked against the European
limits (RadarConfig.check_eu); if they fail, the radar is not started.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

from radarref import adcfile
from radarref.config import RadarConfig, Room

# BGT60TR13C TX power level (0-31). At maximum, the EIRP of the chip with its
# integrated antennas stays below 20 dBm according to its datasheet (check the
# current revision). The lowest level that meets criterion P1 is used.
TX_POWER_LEVEL = 31


def kit_config(cfg: RadarConfig, tx_power: int):
    from ifxradarsdk.fmcw.types import FmcwSequenceChirp, FmcwSimpleSequenceConfig
    return FmcwSimpleSequenceConfig(
        frame_repetition_time_s=1.0 / cfg.frame_rate_hz,
        chirp_repetition_time_s=cfg.t_chirp_s,
        num_chirps=cfg.n_chirps,
        tdm_mimo=False,
        chirp=FmcwSequenceChirp(
            start_frequency_Hz=cfg.f_start_hz,
            end_frequency_Hz=cfg.f_start_hz + cfg.bandwidth_hz,
            sample_rate_Hz=cfg.fs_hz,
            num_samples=cfg.n_samples,
            rx_mask=0b111,           # RX1-RX3
            tx_mask=1,
            tx_power_level=tx_power,
            lp_cutoff_Hz=500000,
            hp_cutoff_Hz=80000,
            if_gain_dB=33,
        ))


class KitRadar:
    """Minimal kit wrapper. Adjusts the ramp so that the *sampled* bandwidth
    equals RadarConfig's (the range resolution depends on it)."""

    def __init__(self, cfg: RadarConfig, tx_power: int):
        from ifxradarsdk.fmcw import DeviceFmcw
        self.dev = DeviceFmcw()
        self.cfg = cfg
        conf = kit_config(cfg, tx_power)
        bw = self.dev.get_chirp_sampling_bandwidth(conf.chirp)
        span = conf.chirp.end_frequency_Hz - conf.chirp.start_frequency_Hz
        conf.chirp.end_frequency_Hz = conf.chirp.start_frequency_Hz + span * cfg.bandwidth_hz / bw
        if conf.chirp.end_frequency_Hz > cfg.EU_F_MAX or conf.chirp.start_frequency_Hz < cfg.EU_F_MIN:
            raise SystemExit("the adjusted ramp would leave 57-64 GHz: not transmitting")
        tmin = self.dev.get_minimum_chirp_repetition_time(cfg.n_samples, cfg.fs_hz)
        if cfg.t_chirp_s < tmin:
            raise SystemExit(f"t_chirp {cfg.t_chirp_s * 1e6:.0f} us < chip minimum {tmin * 1e6:.0f} us")
        seq = self.dev.create_simple_sequence(conf)
        self.dev.set_acquisition_sequence(seq)
        self.meta = {
            "uuid": self.dev.get_board_uuid(),
            "sensor": str(self.dev.get_sensor_type()),
            "firmware": self.dev.get_firmware_information(),
            "ramp_Hz": [conf.chirp.start_frequency_Hz, conf.chirp.end_frequency_Hz],
            "sampled_bandwidth_Hz": self.dev.get_chirp_sampling_bandwidth(conf.chirp),
            "sampled_center_Hz": self.dev.get_chirp_sampling_center_frequency(conf.chirp),
            "tx_power_level": tx_power,
        }

    def frame(self) -> np.ndarray:
        cube = self.dev.get_next_frame(timeout_ms=1000)[0]       # (rx, chirps, samples), 0..1
        return to_signed(cube)

    def temperature(self) -> float:
        return self.dev.get_temperature()


def to_signed(cube: np.ndarray) -> np.ndarray:
    """0..1 (unsigned 12-bit ADC) -> ±1 with the per-chirp DC removed,
    the scale the reference and the firmware expect (counts/2047)."""
    x = (np.asarray(cube, np.float64) - np.mean(cube, axis=-1, keepdims=True)) * 4095.0 / 2047.0
    return np.round(np.clip(x, -1, 1) * 2047) / 2047


class SimRadar:
    """Stand-in for the kit to test the tool without hardware."""

    def __init__(self, cfg: RadarConfig):
        from radarref import scenarios
        from radarref.sim import Simulator
        scene, _, _ = scenarios.fall()
        self.sim = Simulator(scene, cfg)
        self.i = 0
        self.meta = {"uuid": "SIMULATED", "sensor": "radarref simulator"}

    def frame(self) -> np.ndarray:
        # same path as the kit: unsigned 0..1 and conversion
        f = self.sim.frame(self.i / 10)
        self.i += 1
        return to_signed(f * 2047 / 4095 + 0.5)

    def temperature(self) -> float:
        return float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=dt.datetime.now().strftime("session_%Y%m%d_%H%M%S"))
    ap.add_argument("--subject", default="", help="pseudonymous code, e.g. S03 (never the name)")
    ap.add_argument("--room", default="")
    ap.add_argument("--consent", default="", help="reference of the signed consent form")
    ap.add_argument("--height", type=float, default=2.6, help="mounting height (m)")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--out", default="data_real")
    ap.add_argument("--tx", type=int, default=TX_POWER_LEVEL)
    ap.add_argument("--simulated", action="store_true")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args(argv)
    if not a.simulated and a.subject and not a.consent:
        raise SystemExit("subject given but no consent reference: not recording (docs/data-protocol.md)")
    cfg = RadarConfig()
    cfg.check_eu()
    room = Room(mount_h=a.height)
    radar = SimRadar(cfg) if a.simulated else KitRadar(cfg, a.tx)
    pipe = None
    if a.live:
        from radarref.pipeline import Pipeline
        pipe = Pipeline(room, cfg)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n = int(a.seconds * cfg.frame_rate_hz)
    frames, t0, temps = [], time.time(), []
    for i in range(n):
        frames.append(radar.frame())
        if i % 50 == 0:
            temps.append(radar.temperature())
        if pipe is not None:
            o = pipe.step(i / cfg.frame_rate_hz, frames[-1])
            if i % 10 == 0:
                pts = " ".join(f"#{tid}({f[0]:+.1f},{f[1]:+.1f},z{f[2]:.1f})" for tid, _, f in o.tracks)
                print(f"t={i / 10:6.1f}s people={o.count} {pts}", flush=True)
    path = out / f"{a.session}.rfad"
    adcfile.write(path, room, frames)
    meta = {"session": a.session, "subject": a.subject, "room": a.room, "consent": a.consent,
            "start_utc": dt.datetime.utcfromtimestamp(t0).isoformat() + "Z", "duration_s": time.time() - t0,
            "frames": n, "height_m": a.height, "radar_config": {k: getattr(cfg, k) for k in (
                "f_start_hz", "bandwidth_hz", "n_samples", "fs_hz", "n_chirps", "t_chirp_s", "frame_rate_hz")},
            "device": radar.meta, "temperature_C": [t for t in temps if t == t],
            "contract": "features_v1", "tool": "ml/capture_kit.py"}
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str),
                                         encoding="utf-8")
    print(f"{n} frames -> {path}")
    return path


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
