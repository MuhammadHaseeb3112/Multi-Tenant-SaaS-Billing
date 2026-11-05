from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "monthly_price",
        "annual_price",
        "api_request_limit",
        "overage_price_per_1000",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "code",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "plan",
        "status",
        "interval",
        "trial_end",
        "current_period_end",
        "cancel_at_period_end",
        "created_at",
    )

    list_filter = (
        "status",
        "interval",
        "cancel_at_period_end",
    )

    search_fields = (
        "organization__name",
        "organization__slug",
        "stripe_customer_id",
        "stripe_subscription_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )