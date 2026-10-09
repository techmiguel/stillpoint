"""Builds the firmware C code on the PC and compares it with the Python reference."""
import re
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ml"))

import build_host  # noqa: E402


class ModelHeaderTest(unittest.TestCase):
    def test_model_hash_matches_exported_tflite(self):
        """nn_model.h must come from the same .tflite the reference uses (ModelHash in Matter)."""
        h = (ROOT / "firmware/src/nn_model.h").read_text(encoding="utf-8")
        got = int(re.search(r"#define NN_MODEL_HASH32 0x([0-9A-F]+)u", h).group(1), 16)
        tfl = ROOT / "ml/artifacts/synth_v1/model_int8.tflite"
        self.assertEqual(got, zlib.crc32(tfl.read_bytes()))


def have_cc() -> bool:
    try:
        build_host.compiler()
        return True
    except SystemExit:
        return False


@unittest.skipUnless(have_cc(), "no C compiler")
class FirmwareCoreTest(unittest.TestCase):
    def test_contract_decision_limits_in_c(self):
        out = build_host.build("test_host")
        r = subprocess.run([str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_int8_inference_matches_tflite(self):
        out = build_host.build("test_nn")
        r = subprocess.run([str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bgt60_fifo_unpack_matches_capture_tool(self):
        import tempfile
        import numpy as np
        sys.path.insert(0, str(ROOT / "ml"))
        from capture_kit import to_signed
        rng = np.random.default_rng(3)
        # real FIFO: unsigned 12 bits, interleaved [chirp][sample][rx], different offset per antenna
        cube = np.clip(rng.normal([[[2048]], [[1900]], [[2200]]], 300, (3, 32, 128)), 0, 4095).round().astype(np.uint16)
        cube[0, 0, :5] = 4095                       # saturation
        fifo = cube.transpose(1, 2, 0).reshape(-1)
        exe = build_host.build("test_bgt60")
        with tempfile.TemporaryDirectory() as d:
            fi, fo = Path(d) / "f.bin", Path(d) / "o.bin"
            fi.write_bytes(fifo.astype("<u2").tobytes())
            subprocess.run([str(exe), str(fi), str(fo)], check=True)
            c_out = np.frombuffer(fo.read_bytes(), "<i2").reshape(3, 32, 128)
        py = np.round(to_signed(cube / 4095.0) * 2047).astype(int)
        np.testing.assert_array_equal(c_out, py)
        # 12-bit FIFO packing: 2 samples in 3 bytes, MSB first
        s = fifo.astype(np.uint32).reshape(-1, 2)
        packed = np.stack([s[:, 0] >> 4, ((s[:, 0] & 0xF) << 4) | (s[:, 1] >> 8), s[:, 1] & 0xFF], 1)
        with tempfile.TemporaryDirectory() as d:
            fi, fo = Path(d) / "p.bin", Path(d) / "o.bin"
            fi.write_bytes(packed.astype(np.uint8).tobytes())
            subprocess.run([str(exe), "-p", str(fi), str(fo)], check=True)
            np.testing.assert_array_equal(np.frombuffer(fo.read_bytes(), "<u2"), fifo)

    def test_diag_stream_cobs_roundtrip(self):
        import tempfile
        import numpy as np
        import diag_reader
        from radarref import contract as ct
        c = ct.load()
        rng = np.random.default_rng(9)
        recs = [ct.pack(c, i, 100 * i, 1, 2, rng.normal(0, 1, c.n) * (i % 3)) for i in range(40)]
        blobs = {"records": b"".join(recs),
                 "zeros_and_long": bytes(300) + bytes(range(1, 256)) * 3 + b"\x00\x01\x00"}
        exe = build_host.build("test_cobs")
        with tempfile.TemporaryDirectory() as d:
            for name, blob in blobs.items():
                blk = c.record_size if name == "records" else len(blob)
                fi, fo = Path(d) / "i.bin", Path(d) / "o.bin"
                fi.write_bytes(blob)
                subprocess.run([str(exe), str(fi), str(fo), str(blk)], check=True)
                dec = b"".join(diag_reader.cobs_decode(fr) for fr in diag_reader.frames([fo.read_bytes()]))
                self.assertEqual(dec, blob, name)
            out = list(diag_reader.records([fo.read_bytes()]))
        self.assertEqual(out, [])   # the second blob is not records: dropped, never invented

    def test_room_config_python_and_c_agree(self):
        """A frame from tools/room_cfg.py is understood by the firmware and the firmware's
        factory block is understood by the tool; both match tools/room_example.json."""
        import json
        import tempfile
        import room_cfg
        exe = build_host.build("test_room_cfg")
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        cfg = json.loads((ROOT / "tools/room_example.json").read_text(encoding="utf-8"))
        cfg["exclusions"] = [[-0.5, 0.25, 1.0, 1.75]]
        with tempfile.TemporaryDirectory() as d:
            fi, fo = Path(d) / "frame.bin", Path(d) / "factory.bin"
            fi.write_bytes(room_cfg.command(cfg))
            r = subprocess.run([str(exe), str(fi), str(fo)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            lines = dict(l.split(" ", 1) for l in r.stdout.strip().splitlines())
            self.assertEqual(lines["status"], "0")
            self.assertEqual([float(v) for v in lines["room"].split()], cfg["room"])
            self.assertEqual([float(v) for v in lines["exclusion"].split()], cfg["exclusions"][0])
            factory = room_cfg.unpack(fo.read_bytes())
        example = json.loads((ROOT / "tools/room_example.json").read_text(encoding="utf-8"))
        self.assertEqual(factory, example)
        bad = bytearray(room_cfg.pack(example))
        bad[7] ^= 1
        with self.assertRaises(room_cfg.ConfigError):
            room_cfg.unpack(bytes(bad))
        with self.assertRaises(room_cfg.ConfigError):
            room_cfg.pack({**example, "mount_height": 1.0})

    def test_full_app_matches_python_end_to_end(self):
        sys.path.insert(0, str(ROOT / "ml"))
        import compare_app
        from radarref.classifier import Classifier
        exe = build_host.build("replay_app")
        clf = Classifier(compare_app.ART)
        scene, dur = compare_app.all_scenes()["fall"]
        r = compare_app.run("fall", scene, dur, exe, clf)
        self.assertEqual(r["count_match"], 1.0)
        self.assertEqual(r["posture_fall_match"], 1.0)
        self.assertEqual(r["alarm_c_s"], r["alarm_python_s"])
        self.assertIsNotNone(r["alarm_c_s"])

    def test_dsp_and_tracker_match_python(self):
        sys.path.insert(0, str(ROOT / "ml"))
        import compare_c
        exe = build_host.build("replay")
        for name in ("fall", "mirror"):
            r = compare_c.run(name, exe)
            self.assertEqual(r["count_match"], 1.0, name)
            self.assertGreaterEqual(r["quantized_identical"], 0.99, name)


if __name__ == "__main__":
    unittest.main()
