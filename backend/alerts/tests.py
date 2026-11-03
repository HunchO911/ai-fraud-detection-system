import uuid
from decimal import Decimal

from django.test import TestCase

from authentication.models import User
from detection.models import DetectionResult
from transactions.models import Transaction

from .models import Alert


class AlertModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="S3cure-Passw0rd!",
            first_name="Test",
            last_name="User",
        )
        txn = Transaction.objects.create(
            user=user,
            amount=Decimal("90000.00"),
            transaction_type=Transaction.TransactionType.TRANSFER,
            channel=Transaction.Channel.MOBILE_APP,
        )
        result = DetectionResult.objects.create(
            transaction=txn,
            xgboost_score=0.91,
            fraud_probability=0.93,
            risk_level=DetectionResult.RiskLevel.CRITICAL,
            model_version="test-model",
        )
        self.alert = Alert.objects.create(
            detection_result=result,
            recipient=user,
            channel=Alert.Channel.EMAIL,
            destination=user.email,
            subject="Suspicious transaction",
            message="We blocked a transfer we think is fraudulent.",
        )

    def test_new_alert_is_pending_with_no_attempts(self):
        self.assertEqual(self.alert.status, Alert.Status.PENDING)
        self.assertEqual(self.alert.attempts, 0)
        self.assertIsNone(self.alert.sent_at)

    def test_mark_sent(self):
        self.alert.mark_sent(provider_message_id="msg-123")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.SENT)
        self.assertEqual(self.alert.provider_message_id, "msg-123")
        self.assertEqual(self.alert.attempts, 1)
        self.assertIsNotNone(self.alert.sent_at)

    def test_mark_failed_then_sent_clears_the_error(self):
        self.alert.mark_failed("SMTP timeout")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.FAILED)
        self.assertEqual(self.alert.error_message, "SMTP timeout")

        self.alert.mark_sent()  # a retry succeeds
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, Alert.Status.SENT)
        self.assertEqual(self.alert.error_message, "")
        self.assertEqual(self.alert.attempts, 2)
