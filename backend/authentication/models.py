"""Custom user model: email login, a role for access control, alert preferences."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# E.164 international format, e.g. +2348012345678 (what SMS providers expect).
phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter the phone number in international format, e.g. +2348012345678.",
)


class UserManager(BaseUserManager):
    """Creates users that log in with an email address instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)  # hashes the password; never stored in plain text
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        # Makes login case-insensitive: ADA@x.com and ada@x.com are the same user.
        return self.get(email__iexact=email)


class User(AbstractBaseUser, PermissionsMixin):
    """
    A person who uses the system.

    `role` drives what they can see:
      - customer: only their own transactions
      - analyst:  every transaction, and can review flagged ones
      - admin:    everything
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ANALYST = "analyst", "Fraud analyst"
        ADMIN = "admin", "Administrator"

    # UUID primary keys can't be guessed or enumerated through the API.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=16, blank=True, validators=[phone_validator])

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    # Which channels this user wants fraud alerts on (used by the alerts app).
    receive_email_alerts = models.BooleanField(default=True)
    receive_sms_alerts = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # can open the Django admin
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]  # asked for by `createsuperuser`

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Store every email lowercased so uniqueness and lookups stay consistent.
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_analyst_or_admin(self) -> bool:
        return self.role in (self.Role.ANALYST, self.Role.ADMIN)

    # Django's admin and some libraries call these two methods.
    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name
