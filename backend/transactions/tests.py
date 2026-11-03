from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from detection.services import ModelNotAvailable

from .models import Transaction

PASSWORD = "S3cure-Passw0rd!"

PAYLOAD = {
    "amount": "25000.00",
    "currency": "ngn",
    "transaction_type": "transfer",
    "channel": "mobile_app",
    "counterparty_account": "0123456789",
    "device_id": "device-abc",
    "country": "ng",
    "city": "Abuja",
}


def make_user(email, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Test", last_name="User", role=role
    )


def make_transaction(user, amount="100.00"):
    return Transaction.objects.create(
        user=user,
        amount=Decimal(amount),
        transaction_type=Transaction.TransactionType.PAYMENT,
        channel=Transaction.Channel.WEB,
    )


class TransactionApiTests(TestCase):
    def setUp(self):
        # These tests are about the API itself. Pretend no trained model exists so
        # a model trained on your machine can't change the results (the scoring
        # flow has its own tests in detection/test_flow.py).
        patcher = mock.patch("detection.services.get_predictor", side_effect=ModelNotAvailable("tests"))
        patcher.start()
        self.addCleanup(patcher.stop)

        cache.clear()
        self.client = APIClient()
        self.customer = make_user("customer@example.com")
        self.other = make_user("other@example.com")
        self.analyst = make_user("analyst@example.com", role=User.Role.ANALYST)
        self.list_url = reverse("transaction-list")

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post(self.list_url, PAYLOAD, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_create_fills_in_server_controlled_fields(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(self.list_url, PAYLOAD, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["currency"], "NGN")  # normalised to upper case
        self.assertEqual(response.data["country"], "NG")
        self.assertEqual(response.data["ip_address"], "127.0.0.1")
        self.assertTrue(response.data["reference"].startswith("TXN-"))
        self.assertEqual(str(response.data["user"]), str(self.customer.pk))

    def test_client_cannot_override_read_only_fields(self):
        self.client.force_authenticate(self.customer)
        payload = {
            **PAYLOAD,
            "user": str(self.other.pk),
            "status": "approved",
            "ip_address": "9.9.9.9",
            "reference": "TXN-CHOSENBYCLIENT",
        }
        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(response.data["user"]), str(self.customer.pk))
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["ip_address"], "127.0.0.1")
        self.assertNotEqual(response.data["reference"], "TXN-CHOSENBYCLIENT")

    def test_amount_must_be_positive(self):
        self.client.force_authenticate(self.customer)
        for bad_amount in ("0", "-5.00"):
            response = self.client.post(
                self.list_url, {**PAYLOAD, "amount": bad_amount}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("amount", response.data)

    def test_invalid_currency_is_rejected(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(self.list_url, {**PAYLOAD, "currency": "NAIRA"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currency", response.data)

    def test_customer_sees_only_own_transactions(self):
        mine = make_transaction(self.customer)
        theirs = make_transaction(self.other)
        self.client.force_authenticate(self.customer)

        listing = self.client.get(self.list_url)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(str(listing.data["results"][0]["id"]), str(mine.pk))

        own = self.client.get(reverse("transaction-detail", args=[mine.pk]))
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        foreign = self.client.get(reverse("transaction-detail", args=[theirs.pk]))
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)

    def test_analyst_sees_all_transactions(self):
        make_transaction(self.customer)
        make_transaction(self.other)
        self.client.force_authenticate(self.analyst)
        self.assertEqual(self.client.get(self.list_url).data["count"], 2)

    def test_transactions_cannot_be_edited_or_deleted(self):
        txn = make_transaction(self.customer)
        self.client.force_authenticate(self.customer)
        url = reverse("transaction-detail", args=[txn.pk])
        self.assertEqual(
            self.client.patch(url, {"amount": "1.00"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
