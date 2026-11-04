"""
A small, TensorFlow-free copy of the trained neural part of the hybrid model.

Why: TensorFlow needs far more memory than a free web host offers. The LSTM is
only a few small matrices, so after training we save those numbers to one tiny
file (`lite_model.npz`, see export_lite.py) and run the same maths with NumPy.

What is inside the file
    the LSTM (64 units) + the two Dense layers   -> LiteLSTM
    the sequence scaler (mean / scale)            -> LiteScaler
    the hybrid combiner (logistic regression)     -> LiteMetaModel

Each class mimics just enough of the original (scikit-learn / Keras) object for
FraudPredictor to use it unchanged. export_lite.py checks that the answers match
the originals before you rely on them.
"""

import numpy as np

from .config import PAD_VALUE


def _sigmoid(x):
    # Split by sign so large negative numbers can't overflow exp().
    out = np.empty_like(x, dtype=np.float64)
    positive = x >= 0
    out[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    e = np.exp(x[~positive])
    out[~positive] = e / (1.0 + e)
    return out


class LiteScaler:
    """Same result as StandardScaler.transform."""

    def __init__(self, mean, scale):
        self.mean_ = np.asarray(mean, dtype=np.float64)
        self.scale_ = np.asarray(scale, dtype=np.float64)

    def transform(self, X):
        return (np.asarray(X, dtype=np.float64) - self.mean_) / self.scale_


class LiteMetaModel:
    """Same result as LogisticRegression.predict_proba."""

    def __init__(self, coef, intercept):
        self.coef_ = np.asarray(coef, dtype=np.float64).reshape(1, -1)
        self.intercept_ = np.asarray(intercept, dtype=np.float64).reshape(-1)

    def predict_proba(self, X):
        p = _sigmoid(np.asarray(X, dtype=np.float64) @ self.coef_.T + self.intercept_).reshape(-1)
        return np.column_stack([1.0 - p, p])


class LiteLSTM:
    """
    Keras `Masking -> LSTM(units) -> Dropout -> Dense(relu) -> Dense(sigmoid)`, run with NumPy.

    Keras stores the LSTM weights as one block per quantity with the four gates side by
    side in the order input, forget, cell, output. A time step that is all PAD_VALUE is
    "masked": the state is carried over unchanged, exactly as Keras does.
    """

    def __init__(self, kernel, recurrent_kernel, bias, dense1_w, dense1_b, dense2_w, dense2_b):
        self.kernel = np.asarray(kernel, dtype=np.float64)                    # (features, 4*units)
        self.recurrent = np.asarray(recurrent_kernel, dtype=np.float64)       # (units, 4*units)
        self.bias = np.asarray(bias, dtype=np.float64)                        # (4*units,)
        self.dense1_w = np.asarray(dense1_w, dtype=np.float64)
        self.dense1_b = np.asarray(dense1_b, dtype=np.float64)
        self.dense2_w = np.asarray(dense2_w, dtype=np.float64)
        self.dense2_b = np.asarray(dense2_b, dtype=np.float64)
        self.units = self.recurrent.shape[0]

    def predict(self, windows):
        """windows: (n, steps, features) -> fraud probabilities, shape (n, 1)."""
        x = np.asarray(windows, dtype=np.float64)
        n, steps, _ = x.shape
        u = self.units
        h = np.zeros((n, u))
        c = np.zeros((n, u))
        for t in range(steps):
            step = x[:, t, :]
            active = ~np.all(step == PAD_VALUE, axis=1)  # False where the slot is padding
            if not active.any():
                continue
            z = step @ self.kernel + h @ self.recurrent + self.bias
            i = _sigmoid(z[:, :u])
            f = _sigmoid(z[:, u : 2 * u])
            g = np.tanh(z[:, 2 * u : 3 * u])
            o = _sigmoid(z[:, 3 * u :])
            c_new = f * c + i * g
            h_new = o * np.tanh(c_new)
            keep = active[:, None]
            c = np.where(keep, c_new, c)
            h = np.where(keep, h_new, h)
        hidden = np.maximum(h @ self.dense1_w + self.dense1_b, 0.0)  # Dense + ReLU (Dropout is off when scoring)
        return _sigmoid(hidden @ self.dense2_w + self.dense2_b)

    # The predictor calls the Keras model like `model(window, training=False)`; allow the same.
    def __call__(self, windows, training=False):
        return self.predict(windows)


def save_lite(path, lstm_weights: dict, scaler_mean, scaler_scale, meta_coef, meta_intercept) -> None:
    np.savez_compressed(
        path,
        **lstm_weights,
        scaler_mean=np.asarray(scaler_mean),
        scaler_scale=np.asarray(scaler_scale),
        meta_coef=np.asarray(meta_coef),
        meta_intercept=np.asarray(meta_intercept),
    )


def load_lite(path):
    """Returns (LiteLSTM, LiteScaler, LiteMetaModel)."""
    with np.load(path) as f:
        lstm = LiteLSTM(
            f["kernel"], f["recurrent_kernel"], f["bias"],
            f["dense1_w"], f["dense1_b"], f["dense2_w"], f["dense2_b"],
        )
        return lstm, LiteScaler(f["scaler_mean"], f["scaler_scale"]), LiteMetaModel(f["meta_coef"], f["meta_intercept"])
