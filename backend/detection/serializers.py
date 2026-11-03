"""Serializers for the dashboard API (analysts and administrators)."""

from django.utils import timezone
from rest_framework import serializers

from alerts.serializers import AlertSerializer
from transactions.models import Transaction

from .model_info import model_info
from .models import DetectionResult, DetectionSettings


class TransactionBriefSerializer(serializers.ModelSerializer):
    """The transaction facts shown in a list row."""

    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "reference",
            "user_email",
            "amount",
            "currency",
            "transaction_type",
            "channel",
            "country",
            "city",
            "timestamp",
            "status",
        )
        read_only_fields = fields


class TransactionFullSerializer(TransactionBriefSerializer):
    """Everything an analyst needs on the detail page."""

    class Meta(TransactionBriefSerializer.Meta):
        fields = TransactionBriefSerializer.Meta.fields + (
            "merchant_name",
            "merchant_category",
            "counterparty_account",
            "device_id",
            "ip_address",
        )
        read_only_fields = fields


class DetectionListSerializer(serializers.ModelSerializer):
    transaction = TransactionBriefSerializer(read_only=True)

    class Meta:
        model = DetectionResult
        fields = (
            "id",
            "created_at",
            "fraud_probability",
            "risk_level",
            "review_status",
            "model_version",
            "transaction",
        )
        read_only_fields = fields


class DetectionDetailSerializer(serializers.ModelSerializer):
    transaction = TransactionFullSerializer(read_only=True)
    alerts = AlertSerializer(many=True, read_only=True)  # the emails / SMS sent because of this
    reviewed_by_email = serializers.SerializerMethodField()
    thresholds = serializers.SerializerMethodField()  # so the score scale matches the current settings

    class Meta:
        model = DetectionResult
        fields = (
            "id",
            "created_at",
            "fraud_probability",
            "thresholds",
            "xgboost_score",
            "lstm_score",
            "risk_level",
            "model_version",
            "top_features",
            "processing_time_ms",
            "review_status",
            "review_notes",
            "reviewed_by_email",
            "reviewed_at",
            "transaction",
            "alerts",
        )
        read_only_fields = fields

    def get_reviewed_by_email(self, obj):
        return obj.reviewed_by.email if obj.reviewed_by else None

    def get_thresholds(self, obj):
        cfg = DetectionSettings.load()
        return {"medium": cfg.medium_threshold, "high": cfg.high_threshold, "critical": cfg.critical_threshold}


class ReviewSerializer(serializers.Serializer):
    """An analyst's decision on a detection."""

    review_status = serializers.ChoiceField(choices=DetectionResult.ReviewStatus.choices)
    review_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def apply(self, detection: DetectionResult, reviewer) -> DetectionResult:
        """Record the decision and move the transaction's status to match."""
        decision = self.validated_data["review_status"]
        detection.review_status = decision
        if "review_notes" in self.validated_data:
            detection.review_notes = self.validated_data["review_notes"]
        if decision == DetectionResult.ReviewStatus.PENDING:  # reopened
            detection.reviewed_by = None
            detection.reviewed_at = None
        else:
            detection.reviewed_by = reviewer
            detection.reviewed_at = timezone.now()
        detection.save()

        txn = detection.transaction
        if decision == DetectionResult.ReviewStatus.CONFIRMED_FRAUD:
            txn.status = Transaction.Status.BLOCKED
        elif decision == DetectionResult.ReviewStatus.FALSE_POSITIVE:
            txn.status = Transaction.Status.APPROVED
        else:
            txn.status = Transaction.Status.FLAGGED if detection.is_flagged else Transaction.Status.APPROVED
        txn.save(update_fields=["status", "updated_at"])
        return detection


class DetectionSettingsSerializer(serializers.ModelSerializer):
    updated_by_email = serializers.SerializerMethodField()
    model_status = serializers.SerializerMethodField()  # read-only facts about the trained model

    class Meta:
        model = DetectionSettings
        fields = (
            "medium_threshold",
            "high_threshold",
            "critical_threshold",
            "email_alerts_enabled",
            "sms_alerts_enabled",
            "email_min_risk",
            "sms_min_risk",
            "notify_customer",
            "notify_analysts",
            "updated_at",
            "updated_by_email",
            "model_status",
        )
        read_only_fields = ("updated_at", "updated_by_email", "model_status")

    def get_updated_by_email(self, obj):
        return obj.updated_by.email if obj.updated_by else None

    def get_model_status(self, obj):
        return model_info()

    def validate(self, attrs):
        # A PATCH may send only one threshold, so compare against the saved values too.
        merged = {
            name: attrs.get(name, getattr(self.instance, name))
            for name in ("medium_threshold", "high_threshold", "critical_threshold")
        }
        if not (0 < merged["medium_threshold"] < merged["high_threshold"] < merged["critical_threshold"] <= 1):
            raise serializers.ValidationError(
                "Risk levels must rise from medium to high to critical, and stay between 0 and 1."
            )
        return attrs
