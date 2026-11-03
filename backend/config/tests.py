"""Smoke tests that the Django admin works for every model (custom user included)."""

import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from alerts.models import Alert
from authentication.models import User
from detection.models import DetectionResult
from transactions.models import Transaction


class AdminSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            email="root@example.com", password="S3cure-Passw0rd!", first_name="Root", last_name="User"
        )
        cls.txn = Transaction.objects.create(
            user=cls.admin,
            amount=Decimal("1500.00"),
            transaction_type=Transaction.TransactionType.PAYMENT,
            channel=Transaction.Channel.WEB,
        )
        cls.result = DetectionResult.objects.create(
            transaction=cls.txn,
            xgboost_score=0.7,
            fraud_probability=0.7,
            risk_level=DetectionResult.RiskLevel.HIGH,
            model_version="test-model",
        )
        cls.alert = Alert.objects.create(
            detection_result=cls.result,
            recipient=cls.admin,
            channel=Alert.Channel.SMS,
            destination="+2348012345678",
            message="Test alert",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_list_pages_load(self):
        for name in (
            "admin:authentication_user_changelist",
            "admin:transactions_transaction_changelist",
            "admin:detection_detectionresult_changelist",
            "admin:alerts_alert_changelist",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_add_and_change_pages_load(self):
        for name, args in (
            ("admin:authentication_user_add", []),
            ("admin:authentication_user_change", [self.admin.pk]),
            ("admin:transactions_transaction_add", []),
            ("admin:transactions_transaction_change", [self.txn.pk]),
            ("admin:detection_detectionresult_change", [self.result.pk]),
            ("admin:alerts_alert_change", [self.alert.pk]),
        ):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_system_generated_records_cannot_be_added_by_hand(self):
        self.assertEqual(self.client.get(reverse("admin:detection_detectionresult_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:alerts_alert_add")).status_code, 403)

    def test_reviewing_a_detection_records_the_reviewer(self):
        url = reverse("admin:detection_detectionresult_change", args=[self.result.pk])
        response = self.client.post(
            url,
            {"review_status": "confirmed_fraud", "review_notes": "Customer confirmed by phone."},
        )
        self.assertEqual(response.status_code, 302)

        self.result.refresh_from_db()
        self.assertEqual(self.result.review_status, DetectionResult.ReviewStatus.CONFIRMED_FRAUD)
        self.assertEqual(self.result.reviewed_by, self.admin)
        self.assertIsNotNone(self.result.reviewed_at)
