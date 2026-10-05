"""Captura de tramas con el kit de evaluación BGT60TR13C (fase F1).

Usa el SDK de radar de Infineon (paquete Python `ifxradarsdk`, se instala con el
propio SDK). Guarda un fichero .rfad (mismo formato que usan la referencia Python
y el reproductor del firmware) y un .json con los metadatos de la sesión.

  python capture_kit.py --sesion S03_R1_a --sujeto S03 --sala R1 --segundos 300
  python capture_kit.py --simulado --segundos 20          # sin kit: dispositivo simulado
  python capture_kit.py ... --en-vivo                       # procesa y muestra recuento al vuelo

Antes de emitir se comprueba que el barrido y la potencia están dentro de lo
permitido en Europa (RadarConfig.check_eu); si no, no se arranca el radar.
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

# Nivel de potencia TX del BGT60TR13C (0-31). Con el máximo, la PIRE del chip con
# sus antenas integradas queda por debajo de 20 dBm según su hoja de datos
# (verificar en la revisión vigente). Se usa el mínimo que cumpla el criterio P1.
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
    """Envoltorio mínimo del kit. Ajusta la rampa para que el ancho de banda
    *muestreado* sea el de RadarConfig (de él depende la resolución en distancia)."""

    def __init__(self, cfg: RadarConfig, tx_power: int):
        from ifxradarsdk.fmcw import DeviceFmcw
        self.dev = DeviceFmcw()
        self.cfg = cfg
        conf = kit_config(cfg, tx_power)
        bw = self.dev.get_chirp_sampling_bandwidth(conf.chirp)
        span = conf.chirp.end_frequency_Hz - conf.chirp.start_frequency_Hz
        conf.chirp.end_frequency_Hz = conf.chirp.start_frequency_Hz + span * cfg.bandwidth_hz / bw
        if conf.chirp.end_frequency_Hz > cfg.EU_F_MAX or conf.chirp.start_frequency_Hz < cfg.EU_F_MIN:
            raise SystemExit("la rampa ajustada saldría de 57-64 GHz: no se emite")
        tmin = self.dev.get_minimum_chirp_repetition_time(cfg.n_samples, cfg.fs_hz)
        if cfg.t_chirp_s < tmin:
            raise SystemExit(f"t_chirp {cfg.t_chirp_s * 1e6:.0f} us < mínimo del chip {tmin * 1e6:.0f} us")
        seq = self.dev.create_simple_sequence(conf)
        self.dev.set_acquisition_sequence(seq)
        self.meta = {
            "uuid": self.dev.get_board_uuid(),
            "sensor": str(self.dev.get_sensor_type()),
            "firmware": self.dev.get_firmware_information(),
            "rampa_Hz": [conf.chirp.start_frequency_Hz, conf.chirp.end_frequency_Hz],
            "ancho_muestreado_Hz": self.dev.get_chirp_sampling_bandwidth(conf.chirp),
            "centro_muestreado_Hz": self.dev.get_chirp_sampling_center_frequency(conf.chirp),
            "tx_power_level": tx_power,
        }

    def frame(self) -> np.ndarray:
        cube = self.dev.get_next_frame(timeout_ms=1000)[0]       # (rx, chirps, muestras), 0..1
        return to_signed(cube)

    def temperature(self) -> float:
        return self.dev.get_temperature()


def to_signed(cube: np.ndarray) -> np.ndarray:
    """0..1 (ADC de 12 bits sin signo) -> ±1 sin componente continua por chirp,
    la escala que esperan la referencia y el firmware (cuentas/2047)."""
    x = (np.asarray(cube, np.float64) - np.mean(cube, axis=-1, keepdims=True)) * 4095.0 / 2047.0
    return np.round(np.clip(x, -1, 1) * 2047) / 2047


class SimRadar:
    """Sustituto del kit para probar la herramienta sin hardware."""

    def __init__(self, cfg: RadarConfig):
        from radarref import scenarios
        from radarref.sim import Simulator
        scene, _, _ = scenarios.fall()
        self.sim = Simulator(scene, cfg)
        self.i = 0
        self.meta = {"uuid": "SIMULADO", "sensor": "simulador radarref"}

    def frame(self) -> np.ndarray:
        # mismo camino que el kit: sin signo 0..1 y conversión
        f = self.sim.frame(self.i / 10)
        self.i += 1
        return to_signed(f * 2047 / 4095 + 0.5)

    def temperature(self) -> float:
        return float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sesion", default=dt.datetime.now().strftime("sesion_%Y%m%d_%H%M%S"))
    ap.add_argument("--sujeto", default="", help="código seudónimo, p. ej. S03 (nunca el nombre)")
    ap.add_argument("--sala", default="")
    ap.add_argument("--consentimiento", default="", help="referencia del consentimiento firmado")
    ap.add_argument("--altura", type=float, default=2.6, help="altura de montaje (m)")
    ap.add_argument("--segundos", type=float, default=60)
    ap.add_argument("--salida", default="data_real")
    ap.add_argument("--tx", type=int, default=TX_POWER_LEVEL)
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--en-vivo", action="store_true")
    a = ap.parse_args(argv)
    if not a.simulado and a.sujeto and not a.consentimiento:
        raise SystemExit("hay sujeto pero no referencia de consentimiento: no se graba (docs/07)")
    cfg = RadarConfig()
    cfg.check_eu()
    room = Room(mount_h=a.altura)
    radar = SimRadar(cfg) if a.simulado else KitRadar(cfg, a.tx)
    pipe = None
    if a.en_vivo:
        from radarref.pipeline import Pipeline
        pipe = Pipeline(room, cfg)
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    n = int(a.segundos * cfg.frame_rate_hz)
    frames, t0, temps = [], time.time(), []
    for i in range(n):
        frames.append(radar.frame())
        if i % 50 == 0:
            temps.append(radar.temperature())
        if pipe is not None:
            o = pipe.step(i / cfg.frame_rate_hz, frames[-1])
            if i % 10 == 0:
                pts = " ".join(f"#{tid}({f[0]:+.1f},{f[1]:+.1f},z{f[2]:.1f})" for tid, _, f in o.tracks)
                print(f"t={i / 10:6.1f}s personas={o.count} {pts}", flush=True)
    path = out / f"{a.sesion}.rfad"
    adcfile.write(path, room, frames)
    meta = {"sesion": a.sesion, "sujeto": a.sujeto, "sala": a.sala, "consentimiento": a.consentimiento,
            "inicio_utc": dt.datetime.utcfromtimestamp(t0).isoformat() + "Z", "duracion_s": time.time() - t0,
            "tramas": n, "altura_m": a.altura, "radar_config": {k: getattr(cfg, k) for k in (
                "f_start_hz", "bandwidth_hz", "n_samples", "fs_hz", "n_chirps", "t_chirp_s", "frame_rate_hz")},
            "dispositivo": radar.meta, "temperatura_C": [t for t in temps if t == t],
            "contrato": "features_v1", "herramienta": "ml/capture_kit.py"}
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str),
                                         encoding="utf-8")
    print(f"{n} tramas -> {path}")
    return path


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
