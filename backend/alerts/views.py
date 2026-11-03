from rest_framework import viewsets

from authentication.permissions import IsAnalystOrAdmin

from .models import Alert
from .serializers import AlertSerializer


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    The delivery log: every email and SMS the system tried to send.
    GET /api/alerts/?status=failed&channel=sms
    """

    permission_classes = [IsAnalystOrAdmin]
    serializer_class = AlertSerializer

    def get_queryset(self):
        queryset = Alert.objects.select_related("recipient")
        params = self.request.query_params
        if params.get("status") in Alert.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("channel") in Alert.Channel.values:
            queryset = queryset.filter(channel=params["channel"])
        return queryset
