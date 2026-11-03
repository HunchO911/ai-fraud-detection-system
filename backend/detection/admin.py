from django.contrib import admin
from django.utils import timezone

from .models import DetectionResult, DetectionSettings


@admin.register(DetectionResult)
class DetectionResultAdmin(admin.ModelAdmin):
    list_display = (
        "transaction",
        "fraud_probability",
        "risk_level",
        "review_status",
        "model_version",
        "created_at",
    )
    list_filter = ("risk_level", "review_status", "model_version")
    search_fields = ("transaction__reference", "transaction__user__email")
    list_select_related = ("transaction",)
    date_hierarchy = "created_at"

    fields = (
        "id",
        "transaction",
        "fraud_probability",
        "risk_level",
        "xgboost_score",
        "lstm_score",
        "model_version",
        "processing_time_ms",
        "top_features",
        "review_status",
        "review_notes",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )
    # Model output is read-only so predictions can't be tampered with. An analyst
    # may only change the review decision and notes.
    readonly_fields = (
        "id",
        "transaction",
        "fraud_probability",
        "risk_level",
        "xgboost_score",
        "lstm_score",
        "model_version",
        "processing_time_ms",
        "top_features",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )

    def has_add_permission(self, request):
        # Results are created by the scoring service, never by hand.
        return False

    def save_model(self, request, obj, form, change):
        # Record who made the review decision, and when.
        if (
            change
            and "review_status" in form.changed_data
            and obj.review_status != DetectionResult.ReviewStatus.PENDING
        ):
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(DetectionSettings)
class DetectionSettingsAdmin(admin.ModelAdmin):
    """The single settings row. Administrators normally edit it on the dashboard's Settings page."""

    def has_add_permission(self, request):
        return not DetectionSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
