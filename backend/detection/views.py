"""
Dashboard API.

    GET  /api/detections/              the alert list (filters: risk, review, search, ordering)
    GET  /api/detections/<id>/         one alert in full: scores, reasons, alerts sent, review
    POST /api/detections/<id>/review/  confirm fraud / mark false positive / reopen
    GET  /api/dashboard/stats/         the last 24 hours at a glance
    GET  /api/settings/                administrator settings and model status
    PATCH /api/settings/               change them
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncHour
from django.utils import timezone
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole, IsAnalystOrAdmin
from transactions.models import Transaction

from .models import RISK_RANK, DetectionResult, DetectionSettings
from .serializers import (
    DetectionDetailSerializer,
    DetectionListSerializer,
    DetectionSettingsSerializer,
    ReviewSerializer,
)

FLAGGED_LEVELS = [DetectionResult.RiskLevel.HIGH, DetectionResult.RiskLevel.CRITICAL]
ORDERINGS = {"created_at", "-created_at", "fraud_probability", "-fraud_probability"}


class DetectionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Alerts for analysts and administrators. Customers do not see model scores."""

    permission_classes = [IsAnalystOrAdmin]

    def get_queryset(self):
        queryset = DetectionResult.objects.select_related(
            "transaction", "transaction__user", "reviewed_by"
        ).prefetch_related("alerts", "alerts__recipient")
        params = self.request.query_params

        risks = [r for r in params.get("risk", "").split(",") if r in RISK_RANK]
        if risks:
            queryset = queryset.filter(risk_level__in=risks)

        review = params.get("review")
        if review in DetectionResult.ReviewStatus.values:
            queryset = queryset.filter(review_status=review)

        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(transaction__reference__icontains=search)
                | Q(transaction__user__email__icontains=search)
                | Q(transaction__counterparty_account__icontains=search)
            )

        ordering = params.get("ordering", "-created_at")
        return queryset.order_by(ordering if ordering in ORDERINGS else "-created_at")

    def get_serializer_class(self):
        return DetectionListSerializer if self.action == "list" else DetectionDetailSerializer

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Body: {"review_status": "confirmed_fraud" | "false_positive" | "pending", "review_notes": "..."}"""
        detection = self.get_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.apply(detection, request.user)
        return Response(DetectionDetailSerializer(detection, context=self.get_serializer_context()).data)


class StatsView(APIView):
    """
    The last 24 hours (this hour and the 23 before it). Analysts and administrators
    see everything; a customer sees only their own transactions.
    """

    def get(self, request):
        now = timezone.now()
        this_hour = timezone.localtime(now).replace(minute=0, second=0, microsecond=0)
        since = this_hour - timedelta(hours=23)

        transactions = Transaction.objects.filter(timestamp__gte=since)
        detections = DetectionResult.objects.filter(transaction__timestamp__gte=since)
        pending = DetectionResult.objects.filter(
            risk_level__in=FLAGGED_LEVELS, review_status=DetectionResult.ReviewStatus.PENDING
        )
        if not request.user.is_analyst_or_admin:
            transactions = transactions.filter(user=request.user)
            detections = detections.filter(transaction__user=request.user)
            pending = pending.filter(transaction__user=request.user)

        risk_counts = {level: 0 for level in RISK_RANK}
        for row in detections.values("risk_level").annotate(n=Count("id")):
            risk_counts[row["risk_level"]] = row["n"]

        buckets = {
            row["hour"]: row
            for row in transactions.annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(
                total=Count("id"),
                flagged=Count("id", filter=Q(detection_result__risk_level__in=FLAGGED_LEVELS)),
            )
        }
        hourly = []
        for offset in range(23, -1, -1):
            hour = this_hour - timedelta(hours=offset)
            row = buckets.get(hour)
            hourly.append(
                {
                    "hour": hour.isoformat(),
                    "total": row["total"] if row else 0,
                    "flagged": row["flagged"] if row else 0,
                }
            )

        return Response(
            {
                "window_hours": 24,
                "transactions": transactions.count(),
                "flagged": risk_counts["high"] + risk_counts["critical"],
                "pending_review": pending.count(),
                "risk_counts": risk_counts,
                "hourly": hourly,
            }
        )


class SettingsView(generics.RetrieveUpdateAPIView):
    """The administrator's settings. PATCH only the fields you want to change."""

    permission_classes = [IsAdminRole]
    serializer_class = DetectionSettingsSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return DetectionSettings.load()

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
