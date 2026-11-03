from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "user",
        "amount",
        "currency",
        "transaction_type",
        "channel",
        "status",
        "timestamp",
    )
    list_filter = ("status", "channel", "transaction_type", "currency")
    search_fields = ("reference", "user__email", "device_id", "counterparty_account")
    date_hierarchy = "timestamp"
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "created_at", "updated_at")
