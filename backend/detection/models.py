"""
DetectionResult: what the hybrid XGBoost + LSTM model decided about a transaction.
DetectionSettings: the few knobs an administrator can change from the dashboard.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Scores are probabilities, so they must stay between 0 and 1.
probability_validators = [MinValueValidator(0.0), MaxValueValidator(1.0)]

# Lets code compare risk levels: RISK_RANK["high"] >= RISK_RANK["medium"].
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class DetectionResult(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        CONFIRMED_FRAUD = "confirmed_fraud", "Confirmed fraud"
        FALSE_POSITIVE = "false_positive", "False positive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # One transaction is scored once. Re-scoring would update this row.
    transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.CASCADE,
        related_name="detection_result",
    )

    # --- Model output ---
    xgboost_score = models.FloatField(validators=probability_validators)
    # Null when the customer has too little history to build an LSTM sequence.
    lstm_score = models.FloatField(null=True, blank=True, validators=probability_validators)
    # The hybrid (combined) probability. This is the number decisions are based on.
    fraud_probability = models.FloatField(validators=probability_validators)
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    model_version = models.CharField(max_length=50)  # which trained model made this call
    # Why the model decided this (e.g. top feature contributions), for analysts.
    top_features = models.JSONField(default=dict, blank=True)
    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)

    # --- Human review (becomes training labels later) ---
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_detections",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["risk_level", "-created_at"], name="det_risk_created_idx"),
            models.Index(fields=["review_status"], name="det_review_status_idx"),
        ]
        constraints = [
            # Enforced by the database itself, not only by Python validators.
            models.CheckConstraint(
                condition=models.Q(fraud_probability__gte=0.0, fraud_probability__lte=1.0),
                name="det_fraud_probability_0_1",
            ),
        ]

    def __str__(self):
        return f"{self.transaction.reference}: {self.risk_level} ({self.fraud_probability:.2f})"

    @classmethod
    def risk_level_for(cls, probability: float) -> str:
        """Translate a fraud probability into a risk level using the current thresholds."""
        cfg = DetectionSettings.load()
        if probability >= cfg.critical_threshold:
            return cls.RiskLevel.CRITICAL
        if probability >= cfg.high_threshold:
            return cls.RiskLevel.HIGH
        if probability >= cfg.medium_threshold:
            return cls.RiskLevel.MEDIUM
        return cls.RiskLevel.LOW

    @property
    def is_flagged(self) -> bool:
        """True when the transaction needs an analyst's attention."""
        return self.risk_level in (self.RiskLevel.HIGH, self.RiskLevel.CRITICAL)


class DetectionSettings(models.Model):
    """
    A single row (always id 1) holding the settings an administrator edits on the
    dashboard's Settings page. Read it with `DetectionSettings.load()`.
    """

    # Risk bands: a probability at or above each value gets that level.
    medium_threshold = models.FloatField(default=0.30, validators=probability_validators)
    high_threshold = models.FloatField(default=0.60, validators=probability_validators)
    critical_threshold = models.FloatField(default=0.85, validators=probability_validators)

    # Alert channels, and the lowest risk level that triggers each one.
    email_alerts_enabled = models.BooleanField(default=True)
    sms_alerts_enabled = models.BooleanField(default=True)
    email_min_risk = models.CharField(
        max_length=10, choices=DetectionResult.RiskLevel.choices, default="high"
    )
    sms_min_risk = models.CharField(
        max_length=10, choices=DetectionResult.RiskLevel.choices, default="critical"
    )

    # Who gets told: the customer who made the transaction, and/or fraud analysts and admins.
    notify_customer = models.BooleanField(default=True)
    notify_analysts = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "Detection settings"
        verbose_name_plural = "Detection settings"

    def __str__(self):
        return "Detection settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # there is only ever one settings row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "DetectionSettings":
        """Return the settings row, creating it from settings.py defaults on first use."""
        defaults = settings.FRAUD_DETECTION["RISK_THRESHOLDS"]
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "medium_threshold": defaults["medium"],
                "high_threshold": defaults["high"],
                "critical_threshold": defaults["critical"],
            },
        )
        return obj
