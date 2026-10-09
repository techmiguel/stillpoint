"""Runs the int8 artifact exactly like the firmware: normalize, quantize the
input, invoke and dequantize the output. Refuses a model from another contract."""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

from . import contract as ct
from .decision import Params, TrackDecision, inputs_from_window


class ModelMismatch(RuntimeError):
    pass


class Classifier:
    def __init__(self, artifact_dir: str | Path, c: ct.Contract | None = None):
        d = Path(artifact_dir)
        self.meta = json.loads((d / "model_meta.json").read_text(encoding="utf-8"))
        self.c = c or ct.load()
        if self.meta["contract_hash32"] != self.c.hash32:
            raise ModelMismatch("model was trained against another contract: not loaded (fail safe)")
        import tensorflow as tf
        # reference kernels: the same as TFLite Micro and firmware/src/nn.c
        self.it = tf.lite.Interpreter(model_content=(d / "model_int8.tflite").read_bytes(),
                                      experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.it.allocate_tensors()
        self.i, self.o = self.it.get_input_details()[0], self.it.get_output_details()[0]
        m = self.meta
        self.used = np.array(m["used_feature_idx"])
        self.mu, self.sd = np.array(m["mean"]), np.array(m["std"])
        self.lo, self.hi = np.array(m["ood_lo"]), np.array(m["ood_hi"])

    def probs(self, win: np.ndarray) -> np.ndarray:
        x = (win[:, self.used] - self.mu) / self.sd
        s, z = self.i["quantization"]
        self.it.set_tensor(self.i["index"], np.clip(np.round(x / s + z), -128, 127).astype(np.int8)[None])
        self.it.invoke()
        so, zo = self.o["quantization"]
        z = (self.it.get_tensor(self.o["index"])[0].astype(np.float64) - zo) * so
        if self.meta.get("output") != "logits":
            return z
        e = np.exp(z - z.max())       # float softmax, same as nn.c
        return e / e.sum()


class Inference:
    """Per-track windows + classifier + decision, at the contract cadence."""

    def __init__(self, clf: Classifier, params: Params = Params()):
        self.clf, self.c = clf, clf.c
        self.win = defaultdict(lambda: deque(maxlen=self.c.window_frames))
        self.dec = defaultdict(lambda: TrackDecision(params))
        self.n = 0
        self.last = {}

    def step(self, frame_out):
        self.n += 1
        alive = set()
        for tid, _, f in frame_out.tracks:
            alive.add(tid)
            self.win[tid].append(ct.dequantize(self.c, ct.quantize(self.c, f)))
        for tid in list(self.win):
            if tid not in alive:
                del self.win[tid]
                self.dec.pop(tid, None)
                self.last.pop(tid, None)
        if self.n % self.c.window_hop_frames:
            return self.last
        for tid in alive:
            if len(self.win[tid]) < self.c.window_frames:
                continue
            w = np.stack(self.win[tid])
            p = self.clf.probs(w)
            inp = inputs_from_window(self.c, w, frame_out.t, p, self.clf.lo, self.clf.hi, self.clf.used)
            self.last[tid] = (p, *self.dec[tid].update(inp))
        return self.last
