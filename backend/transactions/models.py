"""The Transaction model: one row per payment event that must be screened for fraud."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def generate_reference() -> str:
    """Human-friendly unique reference, e.g. TXN-9F2C41AB77D03E15."""
    return f"TXN-{uuid.uuid4().hex[:16].upper()}"


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        TRANSFER = "transfer", "Transfer"
        PAYMENT = "payment", "Payment"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        DEPOSIT = "deposit", "Deposit"

    class Channel(models.TextChoices):
        MOBILE_APP = "mobile_app", "Mobile app"
        WEB = "web", "Web"
        USSD = "ussd", "USSD"
        POS = "pos", "POS terminal"
        ATM = "atm", "ATM"
        CARD_NOT_PRESENT = "card_not_present", "Card not present (online)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending scoring"   # saved, waiting for the AI model
        APPROVED = "approved", "Approved"        # scored as low risk
        FLAGGED = "flagged", "Flagged for review"  # scored high, an analyst must decide
        BLOCKED = "blocked", "Blocked"           # stopped as fraud

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=32, unique=True, default=generate_reference)

    # PROTECT: financial records must never disappear because a user was deleted.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )

    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=3, default="NGN")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices)

    # Context the model uses as features (merchant, destination, device, location).
    merchant_name = models.CharField(max_length=150, blank=True)
    merchant_category = models.CharField(max_length=100, blank=True)
    counterparty_account = models.CharField(max_length=64, blank=True)
    device_id = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)  # ISO 3166-1 alpha-2, e.g. "NG"
    city = models.CharField(max_length=100, blank=True)

    timestamp = models.DateTimeField(default=timezone.now)  # when the transaction happened
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            # The model needs "this user's recent transactions" constantly
            # (velocity features, LSTM sequences), so make that query fast.
            models.Index(fields=["user", "-timestamp"], name="txn_user_timestamp_idx"),
            models.Index(fields=["status"], name="txn_status_idx"),
            models.Index(fields=["-timestamp"], name="txn_timestamp_idx"),
        ]

    def __str__(self):
        return f"{self.reference} ({self.amount} {self.currency})"
