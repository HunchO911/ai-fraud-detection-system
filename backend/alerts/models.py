"""Alert: one email or SMS notification sent because of a detection result."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Alert(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # created, not delivered yet
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    detection_result = models.ForeignKey(
        "detection.DetectionResult", on_delete=models.CASCADE, related_name="alerts"
    )
    # SET_NULL keeps the alert as an audit record even if the user is later removed.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="alerts",
    )

    channel = models.CharField(max_length=10, choices=Channel.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    # Snapshot of where the message went at send time (the user may change details later).
    destination = models.CharField(max_length=254)  # email address or phone number
    subject = models.CharField(max_length=200, blank=True)  # emails only
    message = models.TextField()

    # Delivery tracking, filled in by the sending service.
    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "channel"], name="alert_status_channel_idx"),
            models.Index(fields=["recipient", "-created_at"], name="alert_recipient_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} to {self.destination} [{self.status}]"

    def mark_sent(self, provider_message_id: str = "") -> None:
        """Record a successful delivery attempt."""
        self.status = self.Status.SENT
        self.provider_message_id = provider_message_id
        self.error_message = ""
        self.sent_at = timezone.now()
        self.attempts += 1
        self.save(
            update_fields=[
                "status",
                "provider_message_id",
                "error_message",
                "sent_at",
                "attempts",
                "updated_at",
            ]
        )

    def mark_failed(self, error: str) -> None:
        """Record a failed delivery attempt (the sender may retry later)."""
        self.status = self.Status.FAILED
        self.error_message = str(error)
        self.attempts += 1
        self.save(update_fields=["status", "error_message", "attempts", "updated_at"])
