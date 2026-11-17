"""
What the dashboard's Settings page shows about the trained model.

Reads `ml_artifacts/metadata.json` (written by `python -m fraud_engine.train`)
without loading TensorFlow, so it is instant and works even if the AI libraries
are not installed on the web server.
"""

import json

from django.conf import settings

from fraud_engine.config import ARTIFACTS_DIR
from fraud_engine.rules import MODEL_VERSION


def model_info() -> dict:
    if settings.FRAUD_DETECTION.get("ENGINE", "rules") != "ml":
        return {
            "available": True,
            "engine": "rules",
            "version": MODEL_VERSION,
            "description": "Compares every payment with the customer's own history: the usual amount for "
            "that kind of payment, known devices, countries and payees, time of day and speed.",
        }
    path = ARTIFACTS_DIR / "metadata.json"
    try:
        meta = json.loads(path.read_text())
    except FileNotFoundError:
        return {"available": False}
    except (OSError, ValueError):
        return {"available": False, "error": "metadata.json exists but could not be read."}

    hybrid = next((m for m in meta.get("test_metrics", []) if m.get("model") == "Hybrid"), {})
    return {
        "available": True,
        "engine": "ml",
        "version": meta.get("model_version"),
        "trained_at": meta.get("trained_at"),
        "data_source": meta.get("data_source"),
        "n_transactions": meta.get("n_transactions"),
        "decision_threshold": meta.get("decision_threshold"),
        "hybrid_pr_auc": hybrid.get("pr_auc"),
        "hybrid_precision": hybrid.get("precision"),
        "hybrid_recall": hybrid.get("recall"),
        "hybrid_f1": hybrid.get("f1"),
    }
