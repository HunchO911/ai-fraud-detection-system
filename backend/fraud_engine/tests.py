"""
Tests for the ML pipeline. Run from the backend folder:

    python -m unittest fraud_engine.tests -v

The data, feature and hybrid tests need only pandas + scikit-learn. The final
end-to-end test needs XGBoost and TensorFlow and is skipped without them.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .config import (
    LABEL_COLUMN, PAD_VALUE, RAW_COLUMNS, SEQUENCE_FEATURES, SEQUENCE_LENGTH, TABULAR_FEATURES,
)
from .data import make_synthetic_data
from .features import build_features, build_sequences, fit_sequence_scaler
from .hybrid import best_f1_threshold, combine, fit_meta_model, suggest_risk_thresholds
from .train import time_split_masks


def tx(user, when, amount, device="d1", country="NG", payee="p1", kind="payment", channel="web"):
    return {
        "user_id": user, "timestamp": pd.Timestamp(when, tz="UTC"), "amount": amount,
        "transaction_type": kind, "channel": channel, "device_id": device,
        "country": country, "counterparty_account": payee,
    }


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_synthetic_data(n_users=300, days=40, seed=1)

    def test_shape_and_columns(self):
        self.assertEqual(list(self.data.columns), RAW_COLUMNS + [LABEL_COLUMN])
        self.assertGreater(len(self.data), 5000)

    def test_fraud_rate_is_realistically_small(self):
        rate = self.data[LABEL_COLUMN].mean()
        self.assertTrue(0.002 < rate < 0.05, rate)

    def test_is_reproducible(self):
        again = make_synthetic_data(n_users=300, days=40, seed=1)
        pd.testing.assert_frame_equal(self.data, again)

    def test_no_missing_values_and_positive_amounts(self):
        self.assertFalse(self.data.isna().any().any())
        self.assertTrue((self.data["amount"] > 0).all())


class FeatureTests(unittest.TestCase):
    def test_columns_exist_and_are_finite(self):
        features = build_features(make_synthetic_data(n_users=200, days=30, seed=2))
        for column in TABULAR_FEATURES + SEQUENCE_FEATURES:
            self.assertIn(column, features.columns)
            self.assertTrue(np.isfinite(features[column]).all(), column)

    def test_velocity_gap_and_novelty_on_a_known_example(self):
        rows = [
            tx("a", "2026-03-02 10:00", 100),
            tx("a", "2026-03-02 10:30", 100),                         # +30 min
            tx("a", "2026-03-02 10:45", 100, device="d2"),            # new device
            tx("a", "2026-03-04 09:00", 100, country="GB"),           # new country, >24h later
            tx("a", "2026-03-04 09:10", 100, payee="p2"),             # new payee
        ]
        f = build_features(pd.DataFrame(rows))
        self.assertEqual(f["txn_count_1h"].tolist(), [1, 2, 3, 1, 2])
        self.assertEqual(f["txn_count_24h"].tolist(), [1, 2, 3, 1, 2])
        self.assertEqual(f["new_device"].tolist(), [0, 0, 1, 0, 0])
        self.assertEqual(f["new_country"].tolist(), [0, 0, 0, 1, 0])
        self.assertEqual(f["new_counterparty"].tolist(), [0, 0, 0, 0, 1])
        self.assertAlmostEqual(f["amount_sum_24h"].iloc[2], 300.0)
        self.assertAlmostEqual(np.expm1(f["log_gap_seconds"].iloc[1]), 1800.0, places=3)

    def test_first_transaction_is_never_flagged_new(self):
        f = build_features(pd.DataFrame([tx("a", "2026-03-02 10:00", 50)]))
        self.assertEqual((f["new_device"].iloc[0], f["new_country"].iloc[0]), (0, 0))

    def test_night_uses_lagos_time(self):
        # 23:30 UTC is 00:30 in Lagos (UTC+1) -> night; 12:00 UTC is 13:00 -> not night.
        f = build_features(pd.DataFrame([tx("a", "2026-03-02 23:30", 50),
                                         tx("b", "2026-03-02 12:00", 50)]))
        self.assertEqual(f.set_index("user_id")["is_night"].to_dict(), {"a": 1.0, "b": 0.0})

    def test_unusual_amount_has_high_zscore(self):
        rows = [tx("a", f"2026-03-0{d} 10:00", 1000 + d) for d in range(1, 8)]
        rows.append(tx("a", "2026-03-09 10:00", 500000))
        f = build_features(pd.DataFrame(rows))
        self.assertGreater(f["amount_zscore"].iloc[-1], 3)
        self.assertLess(abs(f["amount_zscore"].iloc[3]), 3)

    def test_no_future_leakage(self):
        """Features of a transaction must not change when LATER transactions are added."""
        data = make_synthetic_data(n_users=60, days=30, seed=3)
        user = data["user_id"].value_counts().index[0]
        history = data[data["user_id"] == user].sort_values("timestamp").reset_index(drop=True)
        full = build_features(history)
        cut = len(history) // 2
        partial = build_features(history.iloc[:cut])
        pd.testing.assert_frame_equal(
            full.iloc[:cut][TABULAR_FEATURES].reset_index(drop=True),
            partial[TABULAR_FEATURES].reset_index(drop=True),
        )

    def test_input_order_does_not_matter(self):
        data = make_synthetic_data(n_users=40, days=20, seed=4)
        shuffled = data.sample(frac=1, random_state=0)
        a, b = build_features(data), build_features(shuffled)
        pd.testing.assert_frame_equal(a[TABULAR_FEATURES], b[TABULAR_FEATURES])


class SequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = build_features(make_synthetic_data(n_users=80, days=30, seed=5))
        cls.scaler = fit_sequence_scaler(cls.df)
        cls.seq = build_sequences(cls.df, cls.scaler)

    def test_shape(self):
        self.assertEqual(self.seq.shape, (len(self.df), SEQUENCE_LENGTH, len(SEQUENCE_FEATURES)))

    def test_last_step_is_the_transaction_itself_and_padding_is_in_front(self):
        position = self.df.groupby("user_id", sort=False).cumcount().to_numpy()
        first_rows = np.flatnonzero(position == 0)
        # A customer's first transaction: all but the last step are padding.
        self.assertTrue((self.seq[first_rows, :-1, :] == PAD_VALUE).all())
        self.assertTrue((self.seq[first_rows, -1, :] != PAD_VALUE).all())

    def test_window_matches_a_manual_lookup(self):
        position = self.df.groupby("user_id", sort=False).cumcount().to_numpy()
        row = int(np.flatnonzero(position >= SEQUENCE_LENGTH + 2)[0])
        expected = self.df.loc[row - SEQUENCE_LENGTH + 1: row, "hour_sin"].to_numpy()
        index = SEQUENCE_FEATURES.index("hour_sin")
        np.testing.assert_allclose(self.seq[row, :, index], expected, rtol=1e-5)

    def test_windows_never_cross_customers(self):
        users = self.df["user_id"].to_numpy()
        position = self.df.groupby("user_id", sort=False).cumcount().to_numpy()
        index = SEQUENCE_FEATURES.index("hour_cos")
        for row in np.flatnonzero(position >= 2)[:50]:
            np.testing.assert_allclose(
                self.seq[row, -3:, index], self.df.loc[row - 2: row, "hour_cos"], rtol=1e-5
            )
            self.assertTrue((users[row - 2: row + 1] == users[row]).all())

    def test_live_window_equals_batch_window(self):
        """Scoring from one customer's history alone must match the big batch window."""
        position = self.df.groupby("user_id", sort=False).cumcount().to_numpy()
        for row in np.flatnonzero(position >= 4)[:40:8]:
            user = self.df.at[row, "user_id"]
            history = self.df[(self.df["user_id"] == user) & (self.df.index <= row)][RAW_COLUMNS]
            live = build_sequences(build_features(history).tail(SEQUENCE_LENGTH), self.scaler)[-1]
            np.testing.assert_allclose(live, self.seq[row], rtol=1e-4, atol=1e-5)


class SplitAndHybridTests(unittest.TestCase):
    def test_time_split_is_chronological_and_complete(self):
        data = make_synthetic_data(n_users=100, days=30, seed=6)
        masks = time_split_masks(data["timestamp"])
        total = sum(m.sum() for m in masks.values())
        self.assertEqual(total, len(data))
        ts = data["timestamp"]
        self.assertLessEqual(ts[masks["train"]].max(), ts[masks["val"]].min())
        self.assertLessEqual(ts[masks["val"]].max(), ts[masks["stack"]].min())
        self.assertLessEqual(ts[masks["stack"]].max(), ts[masks["test"]].min())

    def test_meta_model_learns_to_trust_the_better_model(self):
        rng = np.random.default_rng(0)
        y = (rng.random(4000) < 0.1).astype(int)
        good = np.clip(y * 0.7 + rng.normal(0.15, 0.1, 4000), 0.01, 0.99)   # informative
        noise = rng.random(4000)                                            # useless
        meta = fit_meta_model(good, noise, y)
        self.assertGreater(abs(meta.coef_[0][0]), 5 * abs(meta.coef_[0][1]))
        hybrid = combine(meta, good, noise)
        self.assertTrue(((hybrid >= 0) & (hybrid <= 1)).all())

    def test_best_threshold_and_risk_bands(self):
        rng = np.random.default_rng(1)
        y = (rng.random(5000) < 0.05).astype(int)
        scores = np.clip(y * 0.5 + rng.normal(0.2, 0.15, 5000), 0, 1)
        high = best_f1_threshold(y, scores)
        bands = suggest_risk_thresholds(y, scores, high)
        self.assertTrue(0 < bands["medium"] < bands["high"] < bands["critical"] <= 0.99, bands)


class SignalSanityTests(unittest.TestCase):
    """The synthetic fraud must be learnable but not trivially separable."""

    def test_signal_is_learnable_but_not_trivial(self):
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import average_precision_score

        df = build_features(make_synthetic_data(n_users=800, days=45, seed=7))
        y = df[LABEL_COLUMN].to_numpy()
        masks = time_split_masks(df["timestamp"])
        train, test = masks["train"], masks["test"]
        model = HistGradientBoostingClassifier(random_state=0, class_weight="balanced")
        model.fit(df.loc[train, TABULAR_FEATURES], y[train])
        pr_auc = average_precision_score(y[test], model.predict_proba(df.loc[test, TABULAR_FEATURES])[:, 1])
        base_rate = y[test].mean()
        self.assertGreater(pr_auc, 8 * base_rate, f"too hard: PR-AUC {pr_auc:.3f}")
        self.assertLess(pr_auc, 0.995, f"too easy: PR-AUC {pr_auc:.3f}")


def _has_ml_libraries():
    try:
        import tensorflow  # noqa: F401
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_ml_libraries(), "needs xgboost and tensorflow")
class EndToEndTests(unittest.TestCase):
    def test_train_save_load_predict(self):
        import sys
        from unittest import mock

        from . import train as train_module
        from .predictor import FraudPredictor

        with tempfile.TemporaryDirectory() as out:
            argv = ["train", "--users", "300", "--days", "30", "--epochs", "2", "--out", out]
            with mock.patch.object(sys, "argv", argv):
                train_module.main()
            predictor = FraudPredictor(Path(out))
            data = make_synthetic_data(n_users=20, days=20, seed=9)
            user = data["user_id"].iloc[0]
            result = predictor.predict(data[data["user_id"] == user][RAW_COLUMNS])
            for key in ("xgboost_score", "lstm_score", "fraud_probability", "model_version",
                        "top_features", "processing_time_ms"):
                self.assertIn(key, result)
            self.assertTrue(0.0 <= result["fraud_probability"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
