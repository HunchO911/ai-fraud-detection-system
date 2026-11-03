"""
End-to-end flow tests: a transaction is posted, "scored" by a stand-in model,
and the right status and alerts appear. The real model is replaced by a stub
so these tests need neither TensorFlow nor trained files.
"""

import unittest
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from authentication.models import User
from alerts.models import Alert
from transactions.models import Transaction

from .models import DetectionResult
from .services import ModelNotAvailable, process_transaction, score_pending

try:
    import pandas  # noqa: F401

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

PASSWORD = "S3cure-Passw0rd!"


class StubPredictor:
    """Returns a fixed probability, like the real predictor's dict."""

    def __init__(self, probability):
        self.probability = probability
        self.calls = []

    def predict(self, history):
        self.calls.append(history)
        return {
            "xgboost_score": self.probability,
            "lstm_score": self.probability,
            "fraud_probability": self.probability,
            "model_version": "stub-1",
            "top_features": {"new_device": 1.0},
            "processing_time_ms": 3.0,
        }


PAYLOAD = {
    "amount": "250000.00",
    "transaction_type": "transfer",
    "channel": "mobile_app",
    "counterparty_account": "0123456789",
    "device_id": "device-9",
    "country": "RU",
}


@override_settings(
    ALERTS_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SMS_BACKEND="console",
)
class ScoringFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            email="customer@example.com", password=PASSWORD, first_name="Chidi", phone_number="+2340000000003"
        )
        self.analyst = User.objects.create_user(
            email="analyst@example.com", password=PASSWORD, role=User.Role.ANALYST, phone_number="+2340000000002"
        )

    def use_model(self, probability):
        stub = StubPredictor(probability)
        patches = [
            mock.patch("detection.services.get_predictor", return_value=stub),
            mock.patch("detection.services.build_history", return_value=object()),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return stub

    def post(self):
        self.client.force_authenticate(self.customer)
        return self.client.post(reverse("transaction-list"), PAYLOAD, format="json")

    def test_risky_transaction_is_flagged_and_alerts_go_out(self):
        self.use_model(0.95)
        response = self.post()
        self.assertEqual(response.status_code, 201)

        txn = Transaction.objects.get()
        detection = txn.detection_result
        self.assertEqual(detection.risk_level, "critical")
        self.assertEqual(detection.model_version, "stub-1")
        self.assertEqual(txn.status, Transaction.Status.FLAGGED)
        self.assertEqual(Alert.objects.filter(status="sent").count(), 4)  # email + SMS, customer + analyst
        self.assertEqual(len(mail.outbox), 2)

    def test_customer_sees_the_risk_level_but_not_the_score(self):
        self.use_model(0.95)
        data = self.post().json()
        self.assertEqual(data["detection"], {"risk_level": "critical"})

    def test_normal_transaction_is_approved_quietly(self):
        self.use_model(0.02)
        self.assertEqual(self.post().status_code, 201)
        txn = Transaction.objects.get()
        self.assertEqual(txn.status, Transaction.Status.APPROVED)
        self.assertEqual(txn.detection_result.risk_level, "low")
        self.assertEqual(Alert.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_without_a_model_the_transaction_is_saved_as_pending(self):
        with mock.patch("detection.services.get_predictor", side_effect=ModelNotAvailable("not trained")):
            response = self.post()
        self.assertEqual(response.status_code, 201)
        txn = Transaction.objects.get()
        self.assertEqual(txn.status, Transaction.Status.PENDING)
        self.assertFalse(DetectionResult.objects.exists())

    def test_a_crashing_model_never_breaks_the_api(self):
        with mock.patch("detection.services.get_predictor", side_effect=RuntimeError("boom")):
            self.assertEqual(self.post().status_code, 201)
        self.assertEqual(Transaction.objects.get().status, Transaction.Status.PENDING)

    def test_pending_transactions_can_be_scored_later(self):
        with mock.patch("detection.services.get_predictor", side_effect=ModelNotAvailable("not trained")):
            self.post()
            self.assertEqual(score_pending(), (0, 1))  # still no model
        self.use_model(0.70)
        self.assertEqual(score_pending(), (1, 0))
        txn = Transaction.objects.get()
        self.assertEqual(txn.status, Transaction.Status.FLAGGED)
        self.assertEqual(txn.detection_result.risk_level, "high")
        self.assertEqual(score_pending(), (0, 0))  # nothing left to do

    def test_rescoring_keeps_an_analysts_decision(self):
        self.use_model(0.95)
        self.post()
        txn = Transaction.objects.get()
        txn.status = Transaction.Status.BLOCKED
        txn.save()
        process_transaction(txn)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.Status.BLOCKED)
        self.assertEqual(DetectionResult.objects.count(), 1)


@unittest.skipUnless(HAS_PANDAS, "pandas is not installed")
class BuildHistoryTests(TestCase):
    def test_new_transaction_is_last_and_old_ones_are_left_out(self):
        from datetime import timedelta

        from django.utils import timezone

        from .services import build_history

        user = User.objects.create_user(email="u@example.com", password=PASSWORD)
        now = timezone.now()

        def make(minutes_ago, amount):
            return Transaction.objects.create(
                user=user,
                amount=Decimal(amount),
                transaction_type="transfer",
                channel="mobile_app",
                device_id="d1",
                country="NG",
                timestamp=now - timedelta(minutes=minutes_ago),
            )

        make(60 * 24 * 400, "1.00")  # far older than HISTORY_DAYS: ignored
        make(120, "10.00")
        make(60, "20.00")
        newest = make(0, "30.00")
        other = User.objects.create_user(email="o@example.com", password=PASSWORD)
        Transaction.objects.create(user=other, amount=Decimal("99.00"), transaction_type="transfer",
                                   channel="mobile_app", country="NG")  # another customer: ignored

        frame = build_history(newest)
        self.assertEqual(list(frame["amount"]), [10.0, 20.0, 30.0])
        self.assertEqual(
            list(frame.columns),
            ["user_id", "timestamp", "amount", "transaction_type", "channel", "device_id", "country",
             "counterparty_account"],
        )
