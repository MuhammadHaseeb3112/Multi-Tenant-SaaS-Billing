from django.contrib import admin

from .models import ApiKey, OverageCharge, UsageRecord


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "prefix",
        "created_at",
        "last_used_at",
        "revoked_at",
    )
    list_filter = ("revoked_at",)
    search_fields = ("name", "prefix", "organization__name")
    # The hash is never editable; keys are created from the dashboard.
    readonly_fields = (
        "prefix",
        "key_hash",
        "created_by",
        "created_at",
        "last_used_at",
        "revoked_at",
        "revoked_by",
    )

    def has_add_permission(self, request):
        return False


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "resource",
        "quantity",
        "endpoint",
        "api_key",
        "recorded_at",
    )
    list_filter = ("resource", "endpoint")
    search_fields = ("organization__name",)
    readonly_fields = ("recorded_at",)


@admin.register(OverageCharge)
class OverageChargeAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "period_start",
        "period_end",
        "overage_requests",
        "amount",
        "currency",
        "status",
        "stripe_invoice_id",
    )
    list_filter = ("status",)
    search_fields = (
        "organization__name",
        "stripe_invoice_id",
        "stripe_invoice_item_id",
    )

    # Money records: created only by the billing code.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
