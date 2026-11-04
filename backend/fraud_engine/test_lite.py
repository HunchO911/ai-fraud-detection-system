"""
Tests for the NumPy copy of the neural part (lite.py).

These prove the code is internally correct (masking, gates, save/load) and that
the scaler and combiner match scikit-learn. Matching the real Keras LSTM can only
be checked where TensorFlow is installed: python -m fraud_engine.export_lite does that.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from .config import PAD_VALUE
from .lite import LiteLSTM, LiteMetaModel, LiteScaler, _sigmoid, load_lite, save_lite

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def random_weights(features=6, units=5, seed=0):
    rng = np.random.default_rng(seed)
    return dict(
        kernel=rng.normal(0, 0.6, (features, 4 * units)),
        recurrent_kernel=rng.normal(0, 0.6, (units, 4 * units)),
        bias=rng.normal(0, 0.3, 4 * units),
        dense1_w=rng.normal(0, 0.6, (units, 4)),
        dense1_b=rng.normal(0, 0.3, 4),
        dense2_w=rng.normal(0, 0.6, (4, 1)),
        dense2_b=rng.normal(0, 0.3, 1),
    )


def reference_forward(w, window):
    """A deliberately plain, one-customer, one-step-at-a-time version of the same maths."""
    u = w["recurrent_kernel"].shape[0]
    h, c = np.zeros(u), np.zeros(u)
    sig = lambda v: 1 / (1 + np.exp(-v))  # noqa: E731
    for step in window:
        if np.all(step == PAD_VALUE):
            continue  # masked: state unchanged
        z = step @ w["kernel"] + h @ w["recurrent_kernel"] + w["bias"]
        i, f, g, o = z[:u], z[u : 2 * u], z[2 * u : 3 * u], z[3 * u :]
        c = sig(f) * c + sig(i) * np.tanh(g)
        h = sig(o) * np.tanh(c)
    hidden = np.maximum(h @ w["dense1_w"] + w["dense1_b"], 0)
    return sig(hidden @ w["dense2_w"] + w["dense2_b"])[0]


def make_windows(n, steps=10, features=6, seed=1):
    rng = np.random.default_rng(seed)
    windows = np.full((n, steps, features), PAD_VALUE)
    for row in range(n):
        length = int(rng.integers(1, steps + 1))
        windows[row, steps - length :] = rng.normal(0, 1.5, (length, features))
    return windows


class LiteLSTMTests(unittest.TestCase):
    def test_matches_the_plain_reference_including_padded_histories(self):
        w = random_weights()
        windows = make_windows(60)
        expected = np.array([reference_forward(w, win) for win in windows])
        got = LiteLSTM(**w).predict(windows)[:, 0]
        np.testing.assert_allclose(got, expected, atol=1e-12)

    def test_front_padding_changes_nothing(self):
        w = random_weights()
        model = LiteLSTM(**w)
        real = np.random.default_rng(3).normal(0, 1, (1, 4, 6))
        padded = np.concatenate([np.full((1, 6, 6), PAD_VALUE), real], axis=1)
        np.testing.assert_allclose(model.predict(real), model.predict(padded), atol=1e-12)

    def test_output_is_a_probability_and_callable_like_keras(self):
        model = LiteLSTM(**random_weights())
        out = model(make_windows(20), training=False)
        self.assertEqual(out.shape, (20, 1))
        self.assertTrue(np.all((out > 0) & (out < 1)))

    def test_a_different_history_gives_a_different_answer(self):
        model = LiteLSTM(**random_weights())
        a = make_windows(1, seed=5)
        b = a.copy()
        b[0, -1, :] += 2.0
        self.assertNotAlmostEqual(float(model.predict(a)[0, 0]), float(model.predict(b)[0, 0]), places=4)


class LiteHelpersTests(unittest.TestCase):
    def test_sigmoid_is_stable_at_extremes(self):
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            out = _sigmoid(np.array([-1000.0, -5.0, 0.0, 5.0, 1000.0]))
        np.testing.assert_allclose(out, [0.0, 0.0066929, 0.5, 0.9933071, 1.0], atol=1e-6)

    def test_save_and_load_round_trip(self):
        w = random_weights()
        windows = make_windows(10)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lite_model.npz"
            save_lite(path, w, [1.0, 2.0, 3.0], [0.5, 1.0, 2.0], [[0.4, 0.9]], [-0.1])
            lstm, scaler, meta = load_lite(path)
        np.testing.assert_allclose(lstm.predict(windows), LiteLSTM(**w).predict(windows), atol=1e-12)
        np.testing.assert_allclose(scaler.transform([[2.0, 4.0, 7.0]]), [[2.0, 2.0, 2.0]])
        self.assertEqual(meta.predict_proba(np.zeros((1, 2))).shape, (1, 2))


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn is not installed")
class MatchesScikitLearnTests(unittest.TestCase):
    def test_scaler(self):
        data = np.random.default_rng(0).normal(5, 3, (200, 3))
        sk = StandardScaler().fit(data)
        lite = LiteScaler(sk.mean_, sk.scale_)
        new = np.random.default_rng(1).normal(0, 9, (50, 3))
        np.testing.assert_allclose(lite.transform(new), sk.transform(new), atol=1e-12)

    def test_meta_model(self):
        rng = np.random.default_rng(0)
        X = rng.normal(0, 2, (400, 2))
        y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(0, 1, 400) > 0).astype(int)
        sk = LogisticRegression().fit(X, y)
        lite = LiteMetaModel(sk.coef_, sk.intercept_)
        new = rng.normal(0, 6, (80, 2))
        np.testing.assert_allclose(lite.predict_proba(new), sk.predict_proba(new), atol=1e-12)


class PredictorUsesLiteTests(unittest.TestCase):
    """The predictor picks the lite copy when TensorFlow files are absent (as on the web server)."""

    def make_folder(self, folder):
        path = Path(folder) / "lite_model.npz"
        save_lite(path, random_weights(features=11, units=4), [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [[0.5, 0.5]], [0.0])

    def test_lite_is_loaded_and_usable(self):
        from .predictor import FraudPredictor

        with tempfile.TemporaryDirectory() as folder:
            self.make_folder(folder)
            predictor = object.__new__(FraudPredictor)
            predictor._load_neural_part(Path(folder), lambda names: all((Path(folder) / n).exists() for n in names))
        self.assertEqual(predictor.neural_backend, "lite")
        out = predictor._lstm(make_windows(2, features=11), training=False)
        self.assertEqual(out.shape, (2, 1))

    def test_missing_files_give_a_helpful_error(self):
        from .predictor import FraudPredictor

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError) as caught:
                FraudPredictor(folder)
        self.assertIn("fraud_engine.train", str(caught.exception))


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn is not installed")
class SequencesWorkWithLiteScalerTests(unittest.TestCase):
    def test_build_sequences_is_identical_with_the_lite_scaler(self):
        from .config import SEQUENCE_CONTINUOUS
        from .data import make_synthetic_data
        from .features import build_features, build_sequences, fit_sequence_scaler

        raw = make_synthetic_data(n_users=3, days=20, seed=4)
        features = build_features(raw[["user_id", "timestamp", "amount", "transaction_type", "channel",
                                       "device_id", "country", "counterparty_account"]])
        scaler = fit_sequence_scaler(features)
        lite = LiteScaler(scaler.mean_, scaler.scale_)
        self.assertEqual(len(SEQUENCE_CONTINUOUS), len(scaler.mean_))
        np.testing.assert_allclose(build_sequences(features, lite), build_sequences(features, scaler), atol=1e-5)


if __name__ == "__main__":
    unittest.main()
