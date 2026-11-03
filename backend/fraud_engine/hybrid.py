"""
The hybrid step: combine the XGBoost and LSTM scores into one fraud probability.

Method: stacking. A small logistic regression (the "meta-model") learns how much
to trust each base model, from their scores on data neither model was trained
on. This is usually better than a fixed 50/50 average because it learns, for
example, that the LSTM deserves more weight when it is confident.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve


def _logit(p) -> np.ndarray:
    """Probability -> log-odds. Clipped so a score of exactly 0 or 1 can't produce infinity."""
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 0.999999)
    return np.log(p / (1 - p))


def stack_features(xgb_scores, lstm_scores) -> np.ndarray:
    """The meta-model's two inputs: each base model's score on the log-odds scale."""
    return np.column_stack([_logit(xgb_scores), _logit(lstm_scores)])


def fit_meta_model(xgb_scores, lstm_scores, y_true) -> LogisticRegression:
    """Learn the combination. Use scores from data the base models never trained on."""
    return LogisticRegression(max_iter=1000).fit(stack_features(xgb_scores, lstm_scores), y_true)


def combine(meta_model, xgb_scores, lstm_scores) -> np.ndarray:
    """The hybrid fraud probability for each transaction."""
    return meta_model.predict_proba(stack_features(xgb_scores, lstm_scores))[:, 1]


def best_f1_threshold(y_true, scores) -> float:
    """The score cut-off with the best balance of precision and recall (F1)."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    precision, recall = precision[:-1], recall[:-1]  # the last point has no threshold
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    return float(thresholds[int(np.argmax(f1))])


def suggest_risk_thresholds(y_true, scores, high: float) -> dict:
    """
    Turn the best-F1 cut-off into the three risk bands Django uses
    (settings.FRAUD_DETECTION["RISK_THRESHOLDS"]):

      medium   half the cut-off: worth a look, no action
      high     the best-F1 cut-off: flag for analyst review
      critical the lowest score above `high` where at least 90% of alerts are
               real fraud; falls back to halfway between `high` and 1
    """
    precision, _, thresholds = precision_recall_curve(y_true, scores)
    reliable = (precision[:-1] >= 0.9) & (thresholds >= high)
    critical = float(thresholds[reliable].min()) if reliable.any() else high + (1 - high) / 2
    critical = min(0.99, max(critical, high + 0.05))
    return {
        "medium": round(high / 2, 2),
        "high": round(high, 2),
        "critical": round(critical, 2),
    }
