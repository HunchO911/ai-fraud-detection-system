"""
Create the demo accounts: an admin, an analyst and three customers, each customer with a
hand-written payment history (see detection/demo_data.py for exactly what it contains).

    python manage.py seed_demo
    python manage.py seed_demo --reset      # delete the demo users' transactions and start over

The history is what the history check compares every new payment with. The accounts use a
fake phone number; none of this is real data.
"""

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction
from django.utils import timezone

from authentication.models import User
from detection.demo_data import CITY, COUNTRY, CUSTOMERS, PURPOSES
from detection.models import DetectionResult, DetectionSettings
from fraud_engine.rules import LOCAL
from transactions.models import Transaction

DEFAULT_PASSWORD = "Demo-Passw0rd!"

STAFF = [
    # email, first name, last name, role, phone (fake)
    ("admin@example.com", "Ada", "Admin", User.Role.ADMIN, "+2340000000001"),
    ("analyst@example.com", "Amina", "Analyst", User.Role.ANALYST, "+2340000000002"),
]


def _make_user(email, first, last, role, phone, password, reset, keep_password=False):
    user = User.objects.filter(email=email).first()
    if user is None:
        make = User.objects.create_superuser if role == User.Role.ADMIN else User.objects.create_user
        return make(email=email, password=password, first_name=first, last_name=last, role=role, phone_number=phone)
    if reset:
        if not keep_password:
            user.set_password(password)
        user.first_name, user.last_name, user.phone_number = first, last, phone
        user.save()
    return user


class Command(BaseCommand):
    help = "Create the demo accounts (admin, analyst, three customers) and the customers' payment history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.getenv("DEMO_PASSWORD", DEFAULT_PASSWORD),
            help="password for every demo account (default: the DEMO_PASSWORD variable, or the built-in demo one)",
        )
        parser.add_argument("--users-only", action="store_true", help="create the accounts but no payment history")
        parser.add_argument("--reset", action="store_true", help="delete the demo users' transactions and start over")
        parser.add_argument("--keep-passwords", action="store_true", help="with --reset: leave the accounts' passwords alone")

    def handle(self, *args, **options):
        if not settings.DEBUG and options["password"] == DEFAULT_PASSWORD:
            raise CommandError(
                "Refusing to create accounts with the well-known demo password on a live site. "
                "Set the DEMO_PASSWORD environment variable to a strong password."
            )

        today = timezone.now().astimezone(LOCAL).replace(minute=0, second=0, microsecond=0)

        with db_transaction.atomic():
            for email, first, last, role, phone in STAFF:
                _make_user(email, first, last, role, phone, options["password"], options["reset"], options["keep_passwords"])
                self.stdout.write(f"  {email}: account ready")

            for customer in CUSTOMERS:
                user = _make_user(
                    customer["email"], customer["first_name"], customer["last_name"],
                    User.Role.CUSTOMER, customer["phone"], options["password"], options["reset"],
                    options["keep_passwords"],
                )
                if options["users_only"]:
                    self.stdout.write(f"  {customer['email']}: account ready")
                    continue
                if options["reset"]:
                    Transaction.objects.filter(user=user).delete()  # also removes their detections and alerts
                if Transaction.objects.filter(user=user).exists():
                    self.stdout.write(f"  {customer['email']}: already has history, left as it is")
                    continue
                self._save_history(user, customer, today)

            # Alerts appear inside the dashboard. Email and SMS stay off until you switch them on
            # (Settings page), so nothing is sent anywhere by accident.
            cfg = DetectionSettings.load()
            cfg.email_alerts_enabled = False
            cfg.sms_alerts_enabled = False
            cfg.save()

        self.stdout.write(self.style.SUCCESS("\nDemo accounts (all use the same password):"))
        for email, _, _, role, _ in STAFF:
            self.stdout.write(f"  {email:<22} {role}")
        for customer in CUSTOMERS:
            self.stdout.write(f"  {customer['email']:<22} customer")
        if settings.DEBUG:
            self.stdout.write(f"  password: {options['password']}")
        self.stdout.write("\nNext: start the backend and the dashboard, sign in as admin@example.com, and use 'Make a payment'.")

    def _save_history(self, user, customer, today):
        transactions = []
        for days_ago, hour, purpose, amount, payee in customer["history"]:
            tx_type, category, merchant, channel = PURPOSES[purpose]
            transactions.append(
                Transaction(
                    user=user,
                    amount=Decimal(amount),
                    transaction_type=tx_type,
                    channel=channel,
                    merchant_name=merchant,
                    merchant_category=category,
                    counterparty_account=payee,
                    device_id=customer["device"],
                    country=COUNTRY,
                    city=CITY,
                    timestamp=today.replace(hour=hour) - timedelta(days=days_ago),
                    status=Transaction.Status.APPROVED,
                )
            )
        Transaction.objects.bulk_create(transactions)

        # The history is the customer's established, trusted past: mark each payment Low risk
        # (so the dashboard shows green, not "Scoring") without raising any alert.
        DetectionResult.objects.bulk_create(
            [
                DetectionResult(
                    transaction=t,
                    xgboost_score=0.02,
                    lstm_score=None,
                    fraud_probability=0.02,
                    risk_level=DetectionResult.RiskLevel.LOW,
                    model_version="seed-history",
                    top_features={"Part of the customer's established history (demo data)": -0.1},
                    processing_time_ms=0,
                )
                for t in transactions
            ]
        )
        self.stdout.write(f"  {customer['email']}: {len(transactions)} transactions")
