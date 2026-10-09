"""Builds and runs the firmware test programs on the PC.

Uses, in order: $CC, gcc, clang or `python -m ziglang cc` (pip install ziglang).
Usage: python tools/build_host.py [target ...]   (no arguments: test_host)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware"
BUILD = FW / "build"
CFLAGS = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{FW / 'include'}", f"-I{FW / 'src'}"]

# target -> (test sources, firmware modules)
CORE = ["src/features_pack.c", "src/decision.c"]
DSP = ["src/rf_fft.c", "src/dsp.c", "src/tracker.c"]
NN = ["src/nn.c"]
APP = ["src/app.c"]
TARGETS = {
    "test_host": (["tests/test_host.c"], CORE),
    "replay": (["tests/replay.c"], CORE + DSP + NN + APP),
    "test_nn": (["tests/test_nn.c"], NN),
    "replay_app": (["tests/replay_app.c"], CORE + DSP + NN + APP),
    "test_bgt60": (["tests/test_bgt60.c"], ["src/bgt60_frame.c"]),
    "test_cobs": (["tests/test_cobs.c"], ["src/cobs.c"]),
    "test_room_cfg": (["tests/test_room_cfg.c"], ["src/room_cfg.c", "src/features_pack.c", "src/cobs.c"]),
}


def compiler() -> list[str]:
    if os.environ.get("CC"):
        return os.environ["CC"].split()
    for cc in ("gcc", "clang"):
        if shutil.which(cc):
            return [cc]
    try:
        import ziglang  # noqa: F401
        return [sys.executable, "-m", "ziglang", "cc"]
    except ImportError:
        raise SystemExit("no C compiler: install gcc or `pip install ziglang`")


def exe(name: str) -> Path:
    return BUILD / (name + (".exe" if os.name == "nt" else ""))


def build(name: str) -> Path:
    tests, mods = TARGETS[name]
    srcs = [str(FW / s) for s in tests + mods if (FW / s).exists()]
    BUILD.mkdir(parents=True, exist_ok=True)
    out = exe(name)
    cmd = compiler() + CFLAGS + ["-o", str(out)] + srcs + ["-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"error building {name}:\n{r.stdout}{r.stderr}")
    return out


def main(argv):
    names = argv or ["test_host"]
    for n in names:
        out = build(n)
        if n in ("test_host", "test_nn", "test_room_cfg"):
            r = subprocess.run([str(out)])
            if r.returncode:
                raise SystemExit(r.returncode)
        else:
            print("built", out.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
