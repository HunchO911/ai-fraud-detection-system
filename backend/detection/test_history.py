"""
End-to-end tests of the history check: seeded customers -> a payment through the API ->
the right risk level and status. No model files and no training are involved.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from authentication.models import User
from transactions.models import Transaction

from .demo_data import CUSTOMERS
from .models import DetectionResult

PASSWORD = "S3cure-Passw0rd!"


def airtime(amount, **extra):
    return {
        "amount": str(amount), "transaction_type": "payment", "merchant_category": "airtime",
        "merchant_name": "Airtime top-up", "channel": "mobile_app", "device_id": "chidi-iphone-13",
        "country": "NG", "on_behalf_of": "chidi@example.com", **extra,
    }


@override_settings(ALERTS_ASYNC=False, SMS_BACKEND="console", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HistoryCheckFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", "--password", PASSWORD, stdout=StringIO())
        cls.admin = User.objects.get(email="admin@example.com")
        cls.chidi = User.objects.get(email="chidi@example.com")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def post(self, payload):
        return self.client.post(reverse("transaction-list"), payload, format="json")

    def test_seed_creates_three_customers_with_their_history(self):
        for customer in CUSTOMERS:
            user = User.objects.get(email=customer["email"])
            self.assertEqual(Transaction.objects.filter(user=user).count(), len(customer["history"]))
        self.assertEqual(User.objects.filter(role="customer").count(), 3)

    def test_seeding_again_with_reset_gives_the_same_result(self):
        call_command("seed_demo", "--reset", "--password", PASSWORD, stdout=StringIO())
        self.assertEqual(Transaction.objects.filter(user=self.chidi).count(), len(CUSTOMERS[0]["history"]))

    def test_a_normal_payment_is_approved(self):
        response = self.post(airtime(1500))
        self.assertEqual(response.status_code, 201, response.content)
        txn = Transaction.objects.get(reference=response.json()["reference"])
        self.assertEqual(txn.user, self.chidi)  # recorded against the customer, not the admin
        self.assertEqual(txn.detection_result.risk_level, "low")
        self.assertEqual(txn.status, Transaction.Status.APPROVED)

    def test_an_amount_he_has_never_paid_is_flagged(self):
        response = self.post(airtime(50000))
        txn = Transaction.objects.get(reference=response.json()["reference"])
        self.assertEqual(txn.detection_result.risk_level, "critical")
        self.assertEqual(txn.status, Transaction.Status.FLAGGED)
        self.assertEqual(txn.detection_result.model_version, "history-rules-1")
        reasons = " ".join(txn.detection_result.top_features)
        self.assertIn("their largest airtime", reasons)

    def test_the_medium_band_is_not_flagged(self):
        txn = Transaction.objects.get(reference=self.post(airtime(5000)).json()["reference"])
        self.assertEqual(txn.detection_result.risk_level, "medium")
        self.assertEqual(txn.status, Transaction.Status.APPROVED)

    def test_new_device_from_abroad_is_flagged(self):
        txn = Transaction.objects.get(
            reference=self.post(airtime(1000, device_id="unknown-1", country="RU")).json()["reference"]
        )
        self.assertEqual(txn.detection_result.risk_level, "high")

    def test_the_history_is_not_flagged_itself(self):
        self.assertFalse(DetectionResult.objects.filter(risk_level__in=["high", "critical"]).exists())

    def test_a_customer_cannot_act_as_someone_else(self):
        self.client.force_authenticate(self.chidi)
        response = self.post(airtime(1000, on_behalf_of="ngozi@example.com"))
        self.assertEqual(response.status_code, 400)

    @override_settings(DEMO_MODE=False)
    def test_acting_as_a_customer_can_be_switched_off(self):
        self.assertEqual(self.post(airtime(1000)).status_code, 400)

    def test_unknown_customer(self):
        self.assertEqual(self.post(airtime(1000, on_behalf_of="nobody@example.com")).status_code, 400)

    def test_profiles_say_what_is_normal(self):
        data = self.client.get(reverse("customer-profiles")).json()
        self.assertEqual([c["email"] for c in data], ["chidi@example.com", "ngozi@example.com", "tunde@example.com"])
        chidi = data[0]
        self.assertEqual(chidi["usual_device"], "chidi-iphone-13")
        air = next(p for p in chidi["purposes"] if p["key"] == "airtime")
        self.assertEqual((air["smallest"], air["largest"], air["low_up_to"], air["critical_from"]), (500, 2000, 2000, 20000))
        self.assertIn("0123456789", [p["account"] for p in chidi["payees"]])

    def test_a_customer_sees_only_their_own_profile(self):
        self.client.force_authenticate(self.chidi)
        data = self.client.get(reverse("customer-profiles")).json()
        self.assertEqual([c["email"] for c in data], ["chidi@example.com"])


    def test_a_flagged_payment_does_not_become_the_new_normal(self):
        first = Transaction.objects.get(reference=self.post(airtime(50000)).json()["reference"])
        second = Transaction.objects.get(reference=self.post(airtime(50000)).json()["reference"])
        self.assertEqual(first.detection_result.risk_level, "critical")
        self.assertEqual(second.detection_result.risk_level, "critical")  # not "normal" just because it happened once

    def test_flagged_payments_do_not_change_the_profile(self):
        self.post(airtime(50000))
        data = self.client.get(reverse("customer-profiles")).json()
        air = next(p for p in data[0]["purposes"] if p["key"] == "airtime")
        self.assertEqual(air["largest"], 2000)

    def test_an_analyst_clearing_a_flag_makes_it_normal(self):
        txn = Transaction.objects.get(reference=self.post(airtime(50000)).json()["reference"])
        detection = txn.detection_result
        self.client.post(reverse("detection-review", args=[detection.pk]), {"review_status": "false_positive"}, format="json")
        again = Transaction.objects.get(reference=self.post(airtime(50000)).json()["reference"])
        self.assertEqual(again.detection_result.risk_level, "low")

    def test_reset_restores_the_original_history(self):
        self.post(airtime(50000))
        self.assertEqual(self.client.post(reverse("demo-reset")).status_code, 200)
        self.assertEqual(Transaction.objects.filter(user=self.chidi).count(), len(CUSTOMERS[0]["history"]))
        self.assertTrue(User.objects.get(email="admin@example.com").check_password(PASSWORD))  # password untouched

    def test_only_admins_can_reset(self):
        self.client.force_authenticate(self.chidi)
        self.assertEqual(self.client.post(reverse("demo-reset")).status_code, 403)
