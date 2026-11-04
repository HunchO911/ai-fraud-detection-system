"""
Loads the saved models once and scores live transactions. This is what Django calls.

    from fraud_engine.predictor import get_predictor

    history = pd.DataFrame(...)  # this customer's recent transactions, NEWEST LAST,
                                 # including the one being scored (RAW_COLUMNS)
    result = get_predictor().predict(history)

The returned keys line up with the detection.DetectionResult model fields.
"""

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, RAW_COLUMNS, SEQUENCE_LENGTH, TABULAR_FEATURES
from .features import build_features, build_sequences
from .hybrid import combine

logger = logging.getLogger(__name__)

# Always needed: the XGBoost model and its description.
_BASE_FILES = ("xgboost_model.json", "metadata.json")
# The neural part comes in two forms. The full one needs TensorFlow (training computer);
# the lite one is one small file that needs only NumPy (web server). See lite.py.
_FULL_FILES = ("lstm_model.keras", "sequence_scaler.joblib", "meta_model.joblib")
_LITE_FILE = "lite_model.npz"


class FraudPredictor:
    def __init__(self, artifacts_dir=ARTIFACTS_DIR):
        artifacts_dir = Path(artifacts_dir)
        has = lambda names: all((artifacts_dir / name).exists() for name in names)  # noqa: E731
        missing_base = [name for name in _BASE_FILES if not (artifacts_dir / name).exists()]
        if missing_base or not (has(_FULL_FILES) or has((_LITE_FILE,))):
            raise FileNotFoundError(
                f"Missing model files in {artifacts_dir} (need {list(_BASE_FILES)} plus either "
                f"{list(_FULL_FILES)} or {_LITE_FILE}). Train first with:  python -m fraud_engine.train"
            )

        # Heavy libraries are imported here so merely importing this module is cheap.
        from xgboost import XGBClassifier

        self.metadata = json.loads((artifacts_dir / "metadata.json").read_text())
        self.model_version = self.metadata["model_version"]
        self.decision_threshold = self.metadata["decision_threshold"]
        self._best_iteration = self.metadata["xgboost_best_iteration"]

        self._xgb = XGBClassifier()
        self._xgb.load_model(str(artifacts_dir / "xgboost_model.json"))
        self._load_neural_part(artifacts_dir, has)

    def _load_neural_part(self, artifacts_dir, has) -> None:
        """
        FRAUD_MODEL_BACKEND = "auto" (default): use TensorFlow when it and the full files are
        there, else the lite copy. "lite" forces the lite copy (what the web server uses).
        """
        choice = os.getenv("FRAUD_MODEL_BACKEND", "auto").strip().lower()
        if choice != "lite" and has(_FULL_FILES):
            try:
                import joblib
                from tensorflow import keras

                self._lstm = keras.models.load_model(artifacts_dir / "lstm_model.keras")
                self._scaler = joblib.load(artifacts_dir / "sequence_scaler.joblib")
                self._meta_model = joblib.load(artifacts_dir / "meta_model.joblib")
                self.neural_backend = "tensorflow"
                return
            except ImportError:
                if not has((_LITE_FILE,)):
                    raise
                logger.info("TensorFlow is not installed; using the lite model instead.")
        if not has((_LITE_FILE,)):
            raise FileNotFoundError(
                f"{_LITE_FILE} not found in {artifacts_dir}. Create it with:  python -m fraud_engine.export_lite"
            )
        from .lite import load_lite

        self._lstm, self._scaler, self._meta_model = load_lite(artifacts_dir / _LITE_FILE)
        self.neural_backend = "lite"

    def predict(self, history: pd.DataFrame) -> dict:
        """
        Score the LAST row of `history` (one customer's transactions, oldest first).

        Pass the customer's full recent history, not just the new transaction:
        features such as "new device" and "amount unusual for this customer"
        need to know what they usually do. Use at least their last 90 days.
        """
        started = time.perf_counter()
        if history["user_id"].nunique() != 1:
            raise ValueError("history must contain transactions of exactly one customer.")

        df = build_features(history[RAW_COLUMNS])  # the same code training used
        current = df[TABULAR_FEATURES].iloc[[-1]]
        xgb_prob = float(
            self._xgb.predict_proba(current, iteration_range=(0, self._best_iteration + 1))[0, 1]
        )

        # Only the last SEQUENCE_LENGTH rows matter to the LSTM.
        window = build_sequences(df.tail(SEQUENCE_LENGTH), self._scaler)[-1:]
        lstm_prob = float(np.asarray(self._lstm(window, training=False))[0, 0])

        fraud_probability = float(combine(self._meta_model, [xgb_prob], [lstm_prob])[0])

        return {
            "xgboost_score": xgb_prob,
            "lstm_score": lstm_prob,
            "fraud_probability": fraud_probability,
            "model_version": self.model_version,
            "top_features": self._explain(current),
            "processing_time_ms": int((time.perf_counter() - started) * 1000),
        }

    def _explain(self, current: pd.DataFrame, top_n: int = 5) -> dict:
        """The features that pushed XGBoost's decision most (SHAP-style contributions)."""
        from xgboost import DMatrix

        contributions = self._xgb.get_booster().predict(
            DMatrix(current),
            pred_contribs=True,
            iteration_range=(0, self._best_iteration + 1),
        )[0][:-1]  # last value is the model's baseline, not a feature
        strongest = np.argsort(-np.abs(contributions))[:top_n]
        return {TABULAR_FEATURES[i]: round(float(contributions[i]), 4) for i in strongest}


@lru_cache(maxsize=1)
def get_predictor() -> FraudPredictor:
    """One shared predictor per process: models load on first use, then stay in memory."""
    return FraudPredictor()
