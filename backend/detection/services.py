"""
Scoring: judge a transaction (history check, or the trained model) and store the verdict.

    process_transaction(txn)   score it, then send alerts. Called as soon as a
                               new transaction is saved. It never raises, so a
                               model or mail problem cannot make the API fail.
    score_transaction(txn)     just the scoring part (raises on failure).
    score_pending(limit)       score transactions that were saved while the model
                               was unavailable.
"""

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connections
from django.db import transaction as db_transaction

from transactions.models import Transaction

from .models import DetectionResult

logger = logging.getLogger(__name__)


class ModelNotAvailable(Exception):
    """The trained model files are missing, or its libraries are not installed."""


def get_predictor():
    """
    The detector that scores transactions: the history check (default) or the trained AI model,
    chosen by FRAUD_ENGINE in settings. Imported lazily so Django starts quickly.
    """
    if settings.FRAUD_DETECTION.get("ENGINE", "rules") != "ml":
        from fraud_engine.rules import RulesPredictor

        return RulesPredictor()
    try:
        from fraud_engine.predictor import get_predictor as load

        return load()
    except (FileNotFoundError, ImportError) as exc:
        raise ModelNotAvailable(str(exc)) from exc


def is_trusted(txn: Transaction) -> bool:
    """
    Is this past transaction part of the customer's NORMAL behaviour? Yes when it was approved
    as low risk (or never scored), or an analyst cleared it as a false alarm. A flagged, blocked
    or merely "medium" payment is not trusted, so one odd payment can't teach the system that odd is normal.
    """
    if txn.status != Transaction.Status.APPROVED:
        return False
    detection = getattr(txn, "detection_result", None)
    return (
        detection is None
        or detection.risk_level == DetectionResult.RiskLevel.LOW
        or detection.review_status == DetectionResult.ReviewStatus.FALSE_POSITIVE
    )


def build_history(txn: Transaction):
    """
    The customer's recent transactions (oldest first) with `txn` as the LAST row,
    in the column layout the model was trained on (fraud_engine.config.RAW_COLUMNS).
    The model needs the history to judge things like "new device" or "unusual amount".
    """
    import pandas as pd

    cfg = settings.FRAUD_DETECTION
    earlier = (
        Transaction.objects.select_related("detection_result")
        .filter(
            user_id=txn.user_id,
            timestamp__gte=txn.timestamp - timedelta(days=cfg["HISTORY_DAYS"]),
            timestamp__lte=txn.timestamp,
        )
        .exclude(pk=txn.pk)
        .order_by("-timestamp")[: cfg["HISTORY_MAX_ROWS"]]
    )
    rows = list(earlier)[::-1] + [txn]  # newest last, the transaction being scored at the very end
    return pd.DataFrame(
        [
            {
                "user_id": str(t.user_id),
                "timestamp": t.timestamp,
                "amount": float(t.amount),
                "transaction_type": t.transaction_type,
                "channel": t.channel,
                "device_id": t.device_id,
                "country": t.country,
                "counterparty_account": t.counterparty_account,
                "merchant_category": t.merchant_category,  # what the money is for (the history check uses it)
                "trusted": is_trusted(t),                  # counts as "normal for them"? (see is_trusted)
            }
            for t in rows
        ]
    )


def score_transaction(txn: Transaction) -> DetectionResult:
    """Run the model on `txn`, save the DetectionResult and update the transaction's status."""
    predictor = get_predictor()
    result = predictor.predict(build_history(txn))
    probability = result["fraud_probability"]

    with db_transaction.atomic():
        detection, _ = DetectionResult.objects.update_or_create(
            transaction=txn,
            defaults={
                "xgboost_score": result["xgboost_score"],
                "lstm_score": result["lstm_score"],
                "fraud_probability": probability,
                "risk_level": DetectionResult.risk_level_for(probability),
                "model_version": result["model_version"],
                "top_features": result["top_features"],
                "processing_time_ms": result["processing_time_ms"],
            },
        )
        # Only move a transaction out of "pending"; never undo an analyst's decision.
        if txn.status == Transaction.Status.PENDING:
            txn.status = (
                Transaction.Status.FLAGGED if detection.is_flagged else Transaction.Status.APPROVED
            )
            txn.save(update_fields=["status", "updated_at"])
    return detection


def _send_alerts_safely(detection) -> None:
    try:
        from alerts.services import send_alerts

        send_alerts(detection)
    except Exception:  # noqa: BLE001
        logger.exception("Sending alerts failed for transaction %s", detection.transaction.reference)


def _dispatch_alerts(detection) -> None:
    """
    Send the alerts for a detection. With ALERTS_ASYNC (the default) this happens
    in a background thread after the database commit, so a slow mail server or
    SMS provider never holds up the API response.
    """
    if not getattr(settings, "ALERTS_ASYNC", False):
        _send_alerts_safely(detection)
        return

    def run() -> None:
        try:
            _send_alerts_safely(detection)
        finally:
            connections.close_all()  # this thread opened its own database connection

    db_transaction.on_commit(
        lambda: threading.Thread(target=run, name="send-alerts", daemon=True).start()
    )


def process_transaction(txn: Transaction):
    """
    Score a new transaction and alert people if it looks risky.
    Returns the DetectionResult, or None if it could not be scored.
    """
    try:
        detection = score_transaction(txn)
    except ModelNotAvailable as exc:
        logger.warning(
            "Transaction %s saved but not scored: model unavailable (%s). "
            "Train it with `python -m fraud_engine.train`, then run `python manage.py score_pending`.",
            txn.reference,
            exc,
        )
        return None
    except Exception:  # noqa: BLE001 - a scoring bug must never break the API
        logger.exception("Scoring failed for transaction %s", txn.reference)
        return None

    _dispatch_alerts(detection)
    return detection


def score_pending(limit: int = 100) -> tuple[int, int]:
    """Score transactions still marked pending, oldest first. Returns (scored, failed)."""
    scored = failed = 0
    for txn in Transaction.objects.filter(status=Transaction.Status.PENDING).order_by("timestamp")[:limit]:
        if process_transaction(txn):
            scored += 1
        else:
            failed += 1
    return scored, failed
