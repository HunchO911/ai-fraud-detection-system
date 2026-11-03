from rest_framework import serializers

from detection.models import DetectionResult

from .models import Transaction


class DetectionSummarySerializer(serializers.ModelSerializer):
    """The model's verdict on a transaction, short form (the full one is under /api/detections/)."""

    class Meta:
        model = DetectionResult
        fields = ("id", "fraud_probability", "risk_level", "review_status")
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    """
    What a client may send and see.

    Server-controlled fields are read-only on purpose: a client must not be able
    to pick its own user, status, timestamp or IP address (a fraudster certainly
    would). The view fills these in.
    """

    user_email = serializers.EmailField(source="user.email", read_only=True)
    # null until the model has scored the transaction
    detection = DetectionSummarySerializer(source="detection_result", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "reference",
            "user",
            "user_email",
            "amount",
            "currency",
            "transaction_type",
            "channel",
            "merchant_name",
            "merchant_category",
            "counterparty_account",
            "device_id",
            "ip_address",
            "country",
            "city",
            "timestamp",
            "status",
            "created_at",
            "detection",
        )
        read_only_fields = (
            "id",
            "reference",
            "user",
            "ip_address",
            "timestamp",
            "status",
            "created_at",
        )

    def validate_currency(self, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Use a 3-letter currency code, e.g. NGN.")
        return value

    def validate_country(self, value):
        value = value.strip().upper()
        if value and (len(value) != 2 or not value.isalpha()):
            raise serializers.ValidationError("Use a 2-letter country code, e.g. NG.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = bool(request and request.user.is_authenticated and request.user.is_analyst_or_admin)
        # Customers learn the risk level of their own transactions, but not the
        # raw model score (it would help a fraudster tune an attack).
        if data.get("detection") and not is_staff:
            data["detection"] = {"risk_level": data["detection"]["risk_level"]}
        return data
