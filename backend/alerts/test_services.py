"""Tests for who gets alerted, on which channel, and what happens when delivery fails."""

from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from authentication.models import User
from detection.models import DetectionResult, DetectionSettings
from transactions.models import Transaction

from .models import Alert
from .services import retry_failed, send_alerts

PASSWORD = "S3cure-Passw0rd!"


def make_user(email, role=User.Role.CUSTOMER, phone=""):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Test", last_name="User", role=role, phone_number=phone
    )


def make_detection(user, probability):
    txn = Transaction.objects.create(
        user=user,
        amount=Decimal("250000.00"),
        transaction_type=Transaction.TransactionType.TRANSFER,
        channel=Transaction.Channel.MOBILE_APP,
        counterparty_account="0123456789",
        device_id="device-9",
        country="RU",
    )
    return DetectionResult.objects.create(
        transaction=txn,
        xgboost_score=probability,
        lstm_score=probability,
        fraud_probability=probability,
        risk_level=DetectionResult.risk_level_for(probability),
        model_version="test-model",
        top_features={"new_device": 1.2},
    )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SMS_BACKEND="console",
    FRONTEND_URL="http://dash.test",
)
class SendAlertsTests(TestCase):
    def setUp(self):
        self.customer = make_user("customer@example.com", phone="+2340000000003")
        self.analyst = make_user("analyst@example.com", User.Role.ANALYST, phone="+2340000000002")

    def test_low_and_medium_risk_send_nothing(self):
        for probability in (0.05, 0.40):
            self.assertEqual(send_alerts(make_detection(self.customer, probability)), [])
        self.assertEqual(Alert.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_high_risk_sends_email_but_not_sms(self):
        handled = send_alerts(make_detection(self.customer, 0.70))  # high: email from "high", SMS from "critical"
        self.assertEqual({a.channel for a in handled}, {"email"})
        self.assertEqual({a.recipient for a in handled}, {self.customer, self.analyst})
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(a.status == Alert.Status.SENT for a in handled))

    def test_critical_risk_sends_email_and_sms(self):
        handled = send_alerts(make_detection(self.customer, 0.95))
        self.assertEqual(len(handled), 4)  # 2 people x 2 channels
        self.assertEqual(Alert.objects.filter(channel="sms", status="sent").count(), 2)

    def test_customer_and_analyst_get_different_wording(self):
        detection = make_detection(self.customer, 0.95)
        send_alerts(detection)
        to_customer = Alert.objects.get(recipient=self.customer, channel="email")
        to_analyst = Alert.objects.get(recipient=self.analyst, channel="email")
        self.assertIn("unusual transaction on your account", to_customer.subject)
        self.assertNotIn("/alerts/", to_customer.message)
        self.assertIn("CRITICAL", to_analyst.subject)
        self.assertIn(f"http://dash.test/alerts/{detection.id}", to_analyst.message)

    def test_sending_twice_does_not_duplicate(self):
        detection = make_detection(self.customer, 0.95)
        send_alerts(detection)
        self.assertEqual(send_alerts(detection), [])
        self.assertEqual(Alert.objects.count(), 4)

    def test_settings_control_the_channels_and_audiences(self):
        cfg = DetectionSettings.load()
        cfg.sms_alerts_enabled = False
        cfg.notify_analysts = False
        cfg.save()
        handled = send_alerts(make_detection(self.customer, 0.95))
        self.assertEqual([(a.recipient, a.channel) for a in handled], [(self.customer, "email")])

    def test_lowering_the_email_level_alerts_medium_risk(self):
        cfg = DetectionSettings.load()
        cfg.email_min_risk = "medium"
        cfg.save()
        self.assertEqual(len(send_alerts(make_detection(self.customer, 0.40))), 2)

    def test_user_opt_outs_and_missing_phone_are_respected(self):
        self.customer.receive_sms_alerts = False
        self.customer.save()
        self.analyst.phone_number = ""
        self.analyst.save()
        handled = send_alerts(make_detection(self.customer, 0.95))
        self.assertEqual(
            sorted((a.recipient.email, a.channel) for a in handled),
            [("analyst@example.com", "email"), ("customer@example.com", "email")],
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SMS_BACKEND="console")
class FailureAndRetryTests(TestCase):
    def setUp(self):
        self.customer = make_user("customer@example.com", phone="+2340000000003")
        self.detection = make_detection(self.customer, 0.95)

    def test_a_failing_sms_provider_is_recorded_not_raised(self):
        with mock.patch("alerts.services.get_sms_backend") as backend:
            backend.return_value.send.side_effect = RuntimeError("provider down")
            handled = send_alerts(self.detection)
        sms = next(a for a in handled if a.channel == "sms")
        email = next(a for a in handled if a.channel == "email")
        self.assertEqual(sms.status, Alert.Status.FAILED)
        self.assertIn("provider down", sms.error_message)
        self.assertEqual(sms.attempts, 1)
        self.assertEqual(email.status, Alert.Status.SENT)  # one channel failing does not stop the other

    def test_retry_sends_failed_alerts_and_gives_up_after_max_attempts(self):
        with mock.patch("alerts.services.get_sms_backend") as backend:
            backend.return_value.send.side_effect = RuntimeError("provider down")
            send_alerts(self.detection)
            self.assertEqual(retry_failed(max_attempts=3), (0, 1))  # attempt 2 fails
            self.assertEqual(retry_failed(max_attempts=3), (0, 1))  # attempt 3 fails
            self.assertEqual(retry_failed(max_attempts=3), (0, 0))  # gave up: not tried again
        self.assertEqual(Alert.objects.get(channel="sms").attempts, 3)

    def test_retry_succeeds_once_the_provider_recovers(self):
        with mock.patch("alerts.services.get_sms_backend") as backend:
            backend.return_value.send.side_effect = RuntimeError("provider down")
            send_alerts(self.detection)
        self.assertEqual(retry_failed(), (1, 0))  # the console backend works
        self.assertEqual(Alert.objects.get(channel="sms").status, Alert.Status.SENT)
