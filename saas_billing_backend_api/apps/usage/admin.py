from django.contrib import admin

from .models import ApiKey, OverageCharge, UsageLimitOverride, UsageRecord


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


@admin.register(UsageLimitOverride)
class UsageLimitOverrideAdmin(admin.ModelAdmin):
    """
    Per-organization usage deals. Empty fields use the plan's value;
    start/end dates let you schedule a change for next period.
    """

    list_display = (
        "organization",
        "api_request_limit",
        "overage_price_per_1000",
        "cap_display",
        "starts_at",
        "ends_at",
        "active_now",
        "note",
    )
    list_filter = ("no_overage_cap",)
    search_fields = ("organization__name", "organization__slug", "note")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_by", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("organization", "note")}),
        (
            "Usage terms (leave empty to use the plan's value)",
            {
                "fields": (
                    "api_request_limit",
                    "overage_price_per_1000",
                    "max_overage_requests",
                    "no_overage_cap",
                )
            },
        ),
        (
            "When it applies (leave empty = from now, no end)",
            {"fields": ("starts_at", "ends_at")},
        ),
        ("History", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Overage cap")
    def cap_display(self, obj):
        if obj.no_overage_cap:
            return "No cap"
        if obj.max_overage_requests is None:
            return "Plan's cap"
        return obj.max_overage_requests

    @admin.display(boolean=True, description="Active now")
    def active_now(self, obj):
        return obj.is_active

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
