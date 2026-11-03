"""Tests for the dashboard API: alert list, detail, review, stats and admin settings."""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from transactions.models import Transaction

from .models import DetectionResult, DetectionSettings

PASSWORD = "S3cure-Passw0rd!"


def make_user(email, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Test", last_name="User", role=role
    )


def make_detection(user, probability, **extra):
    txn = Transaction.objects.create(
        user=user,
        amount=Decimal("5000.00"),
        transaction_type=Transaction.TransactionType.TRANSFER,
        channel=Transaction.Channel.MOBILE_APP,
        counterparty_account="0123456789",
        device_id="device-1",
        country="NG",
    )
    return DetectionResult.objects.create(
        transaction=txn,
        xgboost_score=probability,
        lstm_score=probability,
        fraud_probability=probability,
        risk_level=DetectionResult.risk_level_for(probability),
        model_version="test-model",
        top_features={"new_device": 1.1, "amount_zscore": 0.6},
        **extra,
    )


class DashboardApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.customer = make_user("customer@example.com")
        self.analyst = make_user("analyst@example.com", User.Role.ANALYST)
        self.admin = make_user("admin@example.com", User.Role.ADMIN)
        # Created oldest to newest: low, medium, high, critical (default thresholds 0.30 / 0.60 / 0.85).
        self.low = make_detection(self.customer, 0.05)
        self.medium = make_detection(self.customer, 0.40)
        self.high = make_detection(self.customer, 0.70)
        self.critical = make_detection(self.customer, 0.95)


class DetectionListAndDetailTests(DashboardApiTestCase):
    def test_only_analysts_and_admins_can_use_it(self):
        url = reverse("detection-list")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        detail = reverse("detection-detail", args=[self.high.pk])
        self.assertEqual(self.client.get(detail).status_code, status.HTTP_403_FORBIDDEN)
        review = reverse("detection-review", args=[self.high.pk])
        self.assertEqual(
            self.client.post(review, {"review_status": "confirmed_fraud"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        for staff in (self.analyst, self.admin):
            self.client.force_authenticate(staff)
            self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_list_is_newest_first_with_the_fields_a_row_needs(self):
        self.client.force_authenticate(self.analyst)
        response = self.client.get(reverse("detection-list"))
        self.assertEqual(response.data["count"], 4)
        first = response.data["results"][0]
        self.assertEqual(str(first["id"]), str(self.critical.pk))
        self.assertEqual(first["risk_level"], "critical")
        self.assertEqual(first["transaction"]["user_email"], "customer@example.com")
        self.assertEqual(first["transaction"]["reference"], self.critical.transaction.reference)
        self.assertNotIn("top_features", first)  # the heavy detail is only on the detail page

    def test_filter_by_risk(self):
        self.client.force_authenticate(self.analyst)
        url = reverse("detection-list")
        response = self.client.get(url, {"risk": "high,critical"})
        self.assertEqual({r["risk_level"] for r in response.data["results"]}, {"high", "critical"})
        self.assertEqual(self.client.get(url, {"risk": "banana"}).data["count"], 4)  # unknown values are ignored

    def test_filter_by_review_status_and_search(self):
        self.high.review_status = DetectionResult.ReviewStatus.CONFIRMED_FRAUD
        self.high.save()
        self.client.force_authenticate(self.analyst)
        url = reverse("detection-list")
        self.assertEqual(self.client.get(url, {"review": "pending"}).data["count"], 3)
        self.assertEqual(self.client.get(url, {"review": "confirmed_fraud"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"search": self.low.transaction.reference}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"search": "customer@"}).data["count"], 4)
        self.assertEqual(self.client.get(url, {"search": "nobody-here"}).data["count"], 0)

    def test_ordering_by_probability(self):
        self.client.force_authenticate(self.analyst)
        url = reverse("detection-list")
        top = self.client.get(url, {"ordering": "-fraud_probability"}).data["results"][0]
        self.assertEqual(top["risk_level"], "critical")
        bottom = self.client.get(url, {"ordering": "fraud_probability"}).data["results"][0]
        self.assertEqual(bottom["risk_level"], "low")

    def test_page_size_can_be_chosen(self):
        self.client.force_authenticate(self.analyst)
        response = self.client.get(reverse("detection-list"), {"page_size": 2})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 4)

    def test_detail_tells_the_whole_story(self):
        self.client.force_authenticate(self.analyst)
        data = self.client.get(reverse("detection-detail", args=[self.high.pk])).data
        self.assertEqual(data["xgboost_score"], 0.70)
        self.assertEqual(data["top_features"], {"new_device": 1.1, "amount_zscore": 0.6})
        self.assertEqual(data["transaction"]["counterparty_account"], "0123456789")
        self.assertEqual(data["transaction"]["device_id"], "device-1")
        self.assertEqual(data["alerts"], [])
        self.assertIsNone(data["reviewed_by_email"])
        self.assertEqual(data["thresholds"], {"medium": 0.30, "high": 0.60, "critical": 0.85})


class ReviewTests(DashboardApiTestCase):
    def review(self, detection, decision, notes=""):
        url = reverse("detection-review", args=[detection.pk])
        return self.client.post(url, {"review_status": decision, "review_notes": notes}, format="json")

    def test_confirming_fraud_blocks_the_transaction_and_records_who_and_when(self):
        self.client.force_authenticate(self.analyst)
        response = self.review(self.high, "confirmed_fraud", "Customer confirmed by phone.")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["review_status"], "confirmed_fraud")
        self.assertEqual(response.data["reviewed_by_email"], "analyst@example.com")
        self.assertEqual(response.data["review_notes"], "Customer confirmed by phone.")
        self.assertIsNotNone(response.data["reviewed_at"])

        self.high.transaction.refresh_from_db()
        self.assertEqual(self.high.transaction.status, Transaction.Status.BLOCKED)

    def test_false_positive_approves_the_transaction(self):
        self.client.force_authenticate(self.analyst)
        self.review(self.critical, "false_positive")
        self.critical.transaction.refresh_from_db()
        self.assertEqual(self.critical.transaction.status, Transaction.Status.APPROVED)

    def test_reopening_clears_the_reviewer_and_flags_risky_transactions_again(self):
        self.client.force_authenticate(self.analyst)
        self.review(self.critical, "confirmed_fraud")
        response = self.review(self.critical, "pending")
        self.assertEqual(response.data["review_status"], "pending")
        self.assertIsNone(response.data["reviewed_by_email"])
        self.assertIsNone(response.data["reviewed_at"])
        self.critical.transaction.refresh_from_db()
        self.assertEqual(self.critical.transaction.status, Transaction.Status.FLAGGED)

    def test_unknown_decision_is_rejected(self):
        self.client.force_authenticate(self.analyst)
        response = self.review(self.high, "maybe")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("review_status", response.data)


class StatsTests(DashboardApiTestCase):
    def test_staff_see_everything(self):
        self.client.force_authenticate(self.analyst)
        data = self.client.get(reverse("dashboard-stats")).data
        self.assertEqual(data["transactions"], 4)
        self.assertEqual(data["flagged"], 2)  # high + critical
        self.assertEqual(data["pending_review"], 2)
        self.assertEqual(data["risk_counts"], {"low": 1, "medium": 1, "high": 1, "critical": 1})
        self.assertEqual(len(data["hourly"]), 24)
        self.assertEqual(sum(h["total"] for h in data["hourly"]), 4)
        self.assertEqual(sum(h["flagged"] for h in data["hourly"]), 2)

    def test_pending_review_drops_once_reviewed(self):
        self.high.review_status = DetectionResult.ReviewStatus.FALSE_POSITIVE
        self.high.save()
        self.client.force_authenticate(self.analyst)
        self.assertEqual(self.client.get(reverse("dashboard-stats")).data["pending_review"], 1)

    def test_customers_only_see_their_own_numbers(self):
        other = make_user("other@example.com")
        make_detection(other, 0.99)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(reverse("dashboard-stats")).data["transactions"], 4)
        self.client.force_authenticate(other)
        data = self.client.get(reverse("dashboard-stats")).data
        self.assertEqual(data["transactions"], 1)
        self.assertEqual(data["risk_counts"]["critical"], 1)

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse("dashboard-stats")).status_code, status.HTTP_401_UNAUTHORIZED)


class SettingsTests(DashboardApiTestCase):
    url = property(lambda self: reverse("detection-settings"))

    def test_only_admins(self):
        for user in (self.customer, self.analyst):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(
                self.client.patch(self.url, {"high_threshold": 0.5}, format="json").status_code,
                status.HTTP_403_FORBIDDEN,
            )

    def test_admin_reads_defaults_and_model_status(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get(self.url).data
        self.assertEqual(
            (data["medium_threshold"], data["high_threshold"], data["critical_threshold"]), (0.30, 0.60, 0.85)
        )
        self.assertTrue(data["email_alerts_enabled"])
        self.assertEqual(data["email_min_risk"], "high")
        self.assertEqual(data["sms_min_risk"], "critical")
        self.assertIn("available", data["model_status"])

    def test_changing_thresholds_changes_how_new_scores_are_rated(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(DetectionResult.risk_level_for(0.50), "medium")
        response = self.client.patch(
            self.url, {"medium_threshold": 0.2, "high_threshold": 0.45}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_by_email"], "admin@example.com")
        self.assertEqual(DetectionResult.risk_level_for(0.50), "high")

    def test_thresholds_must_rise_and_stay_within_zero_and_one(self):
        self.client.force_authenticate(self.admin)
        for bad in (
            {"medium_threshold": 0.9},                       # above the saved high threshold (0.60)
            {"high_threshold": 0.2},                         # below the saved medium threshold (0.30)
            {"critical_threshold": 1.5},                     # above 1
            {"medium_threshold": 0.7, "high_threshold": 0.7},  # equal
        ):
            response = self.client.patch(self.url, bad, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, bad)
        self.assertEqual(DetectionSettings.load().high_threshold, 0.60)  # nothing was saved

    def test_toggles_and_channels_can_be_changed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self.url,
            {"sms_alerts_enabled": False, "email_min_risk": "medium", "notify_analysts": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        saved = DetectionSettings.load()
        self.assertFalse(saved.sms_alerts_enabled)
        self.assertFalse(saved.notify_analysts)
        self.assertEqual(saved.email_min_risk, "medium")
