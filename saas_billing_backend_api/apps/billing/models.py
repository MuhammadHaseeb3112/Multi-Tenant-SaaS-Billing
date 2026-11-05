
import uuid
from decimal import Decimal

from django.db import models


class Plan(models.Model):
    class Interval(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        ANNUAL = "ANNUAL", "Annual"

    code = models.CharField(
        max_length=50,
        unique=True,
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.TextField(
        blank=True,
    )

    api_request_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum API requests allowed per billing period.",
    )

    # Usage-based (overage) billing. 0 = overage disabled: requests over
    # the limit are rejected (429). > 0 = requests over the limit are
    # allowed for paying subscriptions and billed at period end.
    overage_price_per_1000 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "Price per 1,000 requests above the limit. "
            "0 disables overage (hard limit)."
        ),
    )

    max_overage_requests = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Safety cap on overage requests per period. "
            "Empty = no cap."
        ),
    )
    
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    stripe_product_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )
    stripe_monthly_price_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )
    stripe_annual_price_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["monthly_price", "name"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "TRIALING", "Trialing"
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past Due"
        CANCELED = "CANCELED", "Canceled"
        UNPAID = "UNPAID", "Unpaid"

    class Interval(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        ANNUAL = "ANNUAL", "Annual"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.OneToOneField(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIALING,
    )

    interval = models.CharField(
        max_length=20,
        choices=Interval.choices,
        default=Interval.MONTHLY,
    )

    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
    )

    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    trial_start = models.DateTimeField(
        null=True,
        blank=True,
    )

    trial_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancel_at_period_end = models.BooleanField(
        default=False,
    )

    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    payment_failed_at = models.DateTimeField(
    null=True,
    blank=True,
    )

    payment_retry_count = models.PositiveIntegerField(
        default=0,
    )

    grace_period_end = models.DateTimeField(
        null=True,
        blank=True,
    )

    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name} - {self.plan.name} ({self.status})"