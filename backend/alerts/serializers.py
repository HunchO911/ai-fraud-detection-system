from rest_framework import serializers

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    """One email or SMS that was (or should have been) sent. Read-only."""

    recipient_email = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = (
            "id",
            "detection_result",
            "channel",
            "status",
            "destination",
            "recipient_email",
            "subject",
            "attempts",
            "error_message",
            "sent_at",
            "created_at",
        )
        read_only_fields = fields

    def get_recipient_email(self, obj):
        return obj.recipient.email if obj.recipient else None
