"""
Make the small server copy of the trained model, and PROVE it gives the same answers.

Run once after training, on the computer that has TensorFlow:

    python -m fraud_engine.export_lite

It reads  ml_artifacts/lstm_model.keras, sequence_scaler.joblib, meta_model.joblib
and writes ml_artifacts/lite_model.npz. Then it feeds the same random test
transactions to the original models and to the lite copy and prints how far apart
the answers are. If they differ by more than a tiny amount the export fails, so a
wrong copy can never reach the server unnoticed.
"""

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np

from .config import ARTIFACTS_DIR, PAD_VALUE, SEQUENCE_FEATURES, SEQUENCE_LENGTH
from .lite import load_lite, save_lite

TOLERANCE = 1e-4


def _weights_from_keras(model) -> dict:
    from tensorflow import keras

    lstm_layers = [layer for layer in model.layers if isinstance(layer, keras.layers.LSTM)]
    dense_layers = [layer for layer in model.layers if isinstance(layer, keras.layers.Dense)]
    if len(lstm_layers) != 1 or len(dense_layers) != 2:
        raise SystemExit("Unexpected model shape: expected one LSTM layer followed by two Dense layers.")

    lstm = lstm_layers[0]
    names = {
        "LSTM activation": (lstm.activation.__name__, "tanh"),
        "LSTM recurrent activation": (lstm.recurrent_activation.__name__, "sigmoid"),
        "first Dense activation": (dense_layers[0].activation.__name__, "relu"),
        "second Dense activation": (dense_layers[1].activation.__name__, "sigmoid"),
    }
    for what, (found, wanted) in names.items():
        if found != wanted:
            raise SystemExit(f"The {what} is '{found}', but the lite copy only supports '{wanted}'.")

    kernel, recurrent, bias = lstm.get_weights()
    d1w, d1b = dense_layers[0].get_weights()
    d2w, d2b = dense_layers[1].get_weights()
    return {
        "kernel": kernel, "recurrent_kernel": recurrent, "bias": bias,
        "dense1_w": d1w, "dense1_b": d1b, "dense2_w": d2w, "dense2_b": d2b,
    }


def _random_windows(n: int, seed: int = 0) -> np.ndarray:
    """Random customer histories of different lengths, padded at the front like real ones."""
    rng = np.random.default_rng(seed)
    n_features = len(SEQUENCE_FEATURES)
    windows = np.full((n, SEQUENCE_LENGTH, n_features), PAD_VALUE, dtype=np.float32)
    for row in range(n):
        length = int(rng.integers(1, SEQUENCE_LENGTH + 1))
        windows[row, SEQUENCE_LENGTH - length :, :] = rng.normal(0, 1.5, size=(length, n_features))
    return windows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, default=ARTIFACTS_DIR, help="folder with the trained model files")
    parser.add_argument("--samples", type=int, default=500, help="how many random test histories to compare")
    args = parser.parse_args()

    from tensorflow import keras

    model = keras.models.load_model(args.dir / "lstm_model.keras")
    scaler = joblib.load(args.dir / "sequence_scaler.joblib")
    meta = joblib.load(args.dir / "meta_model.joblib")

    out = args.dir / "lite_model.npz"
    save_lite(out, _weights_from_keras(model), scaler.mean_, scaler.scale_, meta.coef_, meta.intercept_)
    lite_lstm, lite_scaler, lite_meta = load_lite(out)

    windows = _random_windows(args.samples)
    keras_out = np.asarray(model(windows, training=False))
    lstm_diff = float(np.max(np.abs(keras_out - lite_lstm.predict(windows))))

    values = np.random.default_rng(1).normal(0, 3, size=(args.samples, scaler.mean_.shape[0]))
    scaler_diff = float(np.max(np.abs(scaler.transform(values) - lite_scaler.transform(values))))

    scores = np.random.default_rng(2).uniform(0.001, 0.999, size=(args.samples, 2))
    stacked = np.log(scores / (1 - scores))
    meta_diff = float(np.max(np.abs(meta.predict_proba(stacked) - lite_meta.predict_proba(stacked))))

    print(f"Wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"Largest difference vs the original, over {args.samples} random histories:")
    print(f"  LSTM    {lstm_diff:.2e}")
    print(f"  scaler  {scaler_diff:.2e}")
    print(f"  combiner {meta_diff:.2e}")
    if max(lstm_diff, scaler_diff, meta_diff) > TOLERANCE:
        out.unlink()
        sys.exit(f"FAILED: the lite copy differs by more than {TOLERANCE}. File removed; tell the developer.")
    print("OK: the lite copy matches the original.")


if __name__ == "__main__":
    main()
