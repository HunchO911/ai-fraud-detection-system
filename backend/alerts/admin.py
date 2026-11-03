from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Read-only audit view: alerts are created and updated by the alert service."""

    list_display = ("channel", "destination", "status", "attempts", "sent_at", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("destination", "recipient__email", "detection_result__transaction__reference")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # view-only
