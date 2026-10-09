"""Trains the posture/fall classifier and exports the artifact for the NPU.

Artifact (ML -> firmware interface, docs/architecture.md):
  model_int8.tflite      quantized model (int8 input/output)
  model_meta.json        contract hash, features used, normalization,
                         out-of-distribution limits, thresholds, classes
  model_data.h           the .tflite as a C array to link into the firmware

Usage: python train.py --data data/synth_v1.npz --out artifacts/synth_v1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from radarref import contract as ct
from radarref.metrics import macro_f1, wilson

# Absolute position and tracker state stay out of the model: they would tie it
# to the geometry of the training room.
EXCLUDED = ("x", "y", "range", "state")


def build(n_t, n_f, n_cls):
    """Only ops with a direct int8 kernel in TFLite Micro / CMSIS-NN / MVP:
    CONV_2D (+fused bias +ReLU), MAX_POOL_2D, AVERAGE_POOL_2D,
    FULLY_CONNECTED. The softmax is computed outside, in floating point, over the
    dequantized logits (firmware/src/nn.c and radarref/classifier.py)."""
    import tensorflow as tf
    L = tf.keras.layers
    inp = tf.keras.Input((n_t, n_f), name="window")
    x = L.Conv1D(24, 3, padding="same", activation="relu")(inp)
    x = L.MaxPooling1D(2)(x)
    x = L.Conv1D(24, 3, padding="same", activation="relu")(x)
    x = L.MaxPooling1D(2)(x)
    x = L.Conv1D(24, 3, padding="same", activation="relu")(x)
    x = L.AveragePooling1D(n_t // 4)(x)
    x = L.Flatten()(x)
    x = L.Dropout(0.2)(x)
    logits = L.Dense(n_cls, name="logits")(x)
    probs = L.Softmax(name="probs")(logits)
    return tf.keras.Model(inp, probs), tf.keras.Model(inp, logits)


def softmax(z):
    z = np.asarray(z, dtype=np.float64)
    e = np.exp(z - z.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synth_v1.npz")
    ap.add_argument("--out", default="artifacts/synth_v1")
    ap.add_argument("--epochs", type=int, default=60)
    a = ap.parse_args()
    import tensorflow as tf
    tf.keras.utils.set_random_seed(0)

    d = np.load(a.data, allow_pickle=False)
    c = ct.load()
    if int(d["contract_hash"]) != c.hash32:
        raise SystemExit("the dataset was generated against another feature contract")
    labels = [str(s) for s in d["labels"]]
    used = np.array([i for i, n in enumerate(c.names) if n not in EXCLUDED])
    X, y, room, subj = d["X"][:, :, used], d["y"].astype(int), d["room"], d["subject"]
    from make_synth_dataset import TEST_ROOMS, TEST_SUBJECTS, VAL_ROOMS, VAL_SUBJECTS
    te = np.isin(subj, TEST_SUBJECTS) & np.isin(room, TEST_ROOMS)
    va = np.isin(subj, VAL_SUBJECTS) & np.isin(room, VAL_ROOMS)
    tr = ~np.isin(subj, TEST_SUBJECTS + VAL_SUBJECTS) & ~np.isin(room, TEST_ROOMS + VAL_ROOMS)
    assert not (set(subj[tr]) & set(subj[te])) and not (set(room[tr]) & set(room[te]))

    mu = X[tr].reshape(-1, len(used)).mean(0)
    sd = X[tr].reshape(-1, len(used)).std(0) + 1e-6
    flat = X[tr].reshape(-1, len(used))
    lo = np.percentile(flat, 0.5, axis=0) - 0.5 * sd
    hi = np.percentile(flat, 99.5, axis=0) + 0.5 * sd
    Xn = ((X - mu) / sd).astype(np.float32)

    counts = np.bincount(y[tr], minlength=len(labels))
    cw = {k: float(len(y[tr]) / (len(labels) * max(n, 1))) for k, n in enumerate(counts)}
    model, logits_model = build(Xn.shape[1], Xn.shape[2], len(labels))
    model.compile(optimizer=tf.keras.optimizers.Adam(2e-3), loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    model.fit(Xn[tr], y[tr], validation_data=(Xn[va], y[va]), epochs=a.epochs, batch_size=64,
              class_weight=cw, verbose=0,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)])

    # --- int8 export -------------------------------------------------------
    def rep():
        for i in np.random.default_rng(0).choice(np.where(tr)[0], 300):
            yield [Xn[i:i + 1]]
    conv = tf.lite.TFLiteConverter.from_keras_model(logits_model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    tfl = conv.convert()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model_int8.tflite").write_bytes(tfl)

    # reference kernels: the same as TFLite Micro and firmware/src/nn.c
    interp = tf.lite.Interpreter(model_content=tfl,
                                 experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
    interp.allocate_tensors()
    ii, oo = interp.get_input_details()[0], interp.get_output_details()[0]

    def predict_int8(Xb):
        s, z = ii["quantization"]
        so, zo = oo["quantization"]
        res = []
        for x in Xb:
            interp.set_tensor(ii["index"], np.clip(np.round(x / s + z), -128, 127).astype(np.int8)[None])
            interp.invoke()
            res.append((interp.get_tensor(oo["index"])[0].astype(np.float64) - zo) * so)
        return softmax(np.array(res))

    p_f = model.predict(Xn[te], verbose=0)
    p_q = predict_int8(Xn[te])
    yhat = p_q.argmax(1)
    agree = float(np.mean(p_f.argmax(1) == yhat))
    conf = p_q.max(1)
    p_min = 0.6
    abst = conf < p_min
    f1, per = macro_f1(y[te], np.where(abst, -1, yhat), len(labels), ignore=-1)
    fall = labels.index("fall")
    k = int(np.sum((y[te] == fall) & (yhat == fall)))
    n = int(np.sum(y[te] == fall))
    rec = wilson(k, n)
    cm = np.zeros((len(labels), len(labels)), int)
    for t_, p_ in zip(y[te], yhat):
        cm[t_, p_] += 1
    report = {
        "WARNING": "SYNTHETIC dataset: validates the chain, not the product; never publish as a metric",
        "n_train": int(tr.sum()), "n_val": int(va.sum()), "n_test": int(te.sum()),
        "test_subjects": list(TEST_SUBJECTS), "test_rooms": list(TEST_ROOMS),
        "macro_f1_excl_abstentions": round(f1, 3), "f1_per_class": dict(zip(labels, [round(v, 3) for v in per])),
        "abstention_rate": round(float(abst.mean()), 3),
        "fall_window_recall": {"k": k, "n": n, "p": round(rec[0], 3), "ci95": [round(rec[1], 3), round(rec[2], 3)]},
        "int8_vs_float_agreement": round(agree, 4),
        "confusion_matrix(rows=truth)": cm.tolist(), "classes": labels,
        "model_size_bytes": len(tfl),
    }
    meta = {
        "contract_version": c.version, "contract_hash32": c.hash32, "labels": labels,
        "used_feature_idx": used.tolist(), "used_feature_names": [c.names[i] for i in used],
        "mean": mu.tolist(), "std": sd.tolist(), "ood_lo": lo.tolist(), "ood_hi": hi.tolist(),
        "input_quant": list(map(float, ii["quantization"])), "output_quant": list(map(float, oo["quantization"])),
        "p_min": p_min, "window_frames": c.window_frames, "dataset": str(a.data),
        "output": "logits", "softmax": "float, outside the model",
    }
    (out / "model_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    hexes = ",".join(f"0x{b:02x}" for b in tfl)
    (out / "model_data.h").write_text(
        "/* Generated by ml/train.py. Do not edit. */\n#pragma once\n#include <stdint.h>\n"
        f"#define MODEL_CONTRACT_HASH32 0x{c.hash32:08X}u\n"
        f"#define MODEL_DATA_LEN {len(tfl)}u\n"
        f"static const uint8_t model_data[MODEL_DATA_LEN] __attribute__((aligned(16))) = {{{hexes}}};\n",
        encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))
    # the firmware links exactly this model (TFLite Micro and nn.c)
    root = Path(__file__).resolve().parents[1]
    (root / "firmware/src/model_data.h").write_bytes((out / "model_data.h").read_bytes())
    import subprocess
    import sys
    subprocess.run([sys.executable, str(root / "tools/export_nn.py"), str(out), str(a.data)], check=True)


if __name__ == "__main__":
    main()
