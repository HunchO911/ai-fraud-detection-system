import uuid
from decimal import Decimal

from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.test import TestCase

from authentication.models import User
from transactions.models import Transaction

from .models import DetectionResult


def make_transaction():
    user = User.objects.create_user(
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        password="S3cure-Passw0rd!",
        first_name="Test",
        last_name="User",
    )
    return Transaction.objects.create(
        user=user,
        amount=Decimal("5000.00"),
        transaction_type=Transaction.TransactionType.TRANSFER,
        channel=Transaction.Channel.MOBILE_APP,
    )


def make_result(probability, transaction=None):
    return DetectionResult.objects.create(
        transaction=transaction or make_transaction(),
        xgboost_score=probability,
        fraud_probability=probability,
        risk_level=DetectionResult.risk_level_for(probability),
        model_version="test-model",
    )


class RiskLevelTests(TestCase):
    def test_thresholds_map_probabilities_to_levels(self):
        # Default thresholds: medium 0.30, high 0.60, critical 0.85.
        expected = {
            0.00: "low",
            0.29: "low",
            0.30: "medium",
            0.59: "medium",
            0.60: "high",
            0.84: "high",
            0.85: "critical",
            1.00: "critical",
        }
        for probability, level in expected.items():
            self.assertEqual(DetectionResult.risk_level_for(probability), level, probability)

    def test_is_flagged_only_for_high_and_critical(self):
        self.assertFalse(make_result(0.10).is_flagged)
        self.assertFalse(make_result(0.45).is_flagged)
        self.assertTrue(make_result(0.70).is_flagged)
        self.assertTrue(make_result(0.95).is_flagged)


class DetectionResultModelTests(TestCase):
    def test_lstm_score_is_optional(self):
        self.assertIsNone(make_result(0.2).lstm_score)

    def test_database_rejects_probability_above_one(self):
        with self.assertRaises(IntegrityError):
            with db_transaction.atomic():
                make_result(1.5)

    def test_a_transaction_can_only_be_scored_once(self):
        txn = make_transaction()
        make_result(0.2, transaction=txn)
        with self.assertRaises(IntegrityError):
            with db_transaction.atomic():
                make_result(0.9, transaction=txn)

    def test_review_defaults_to_pending(self):
        self.assertEqual(make_result(0.7).review_status, DetectionResult.ReviewStatus.PENDING)
