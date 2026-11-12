import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    """
    Secret key an organization uses to call the metered product API
    (``/api/v1/...``).

    Only a SHA-256 hash of the key is stored. The plaintext key is shown
    once, when it is created. ``prefix`` (first characters of the key)
    is stored so users can recognise a key in the dashboard.
    """

    KEY_PREFIX = "sbk_"
    DISPLAY_PREFIX_LENGTH = 12

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    name = models.CharField(
        max_length=100,
    )

    prefix = models.CharField(
        max_length=20,
        db_index=True,
    )

    key_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_keys",
    )

    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_api_keys",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "revoked_at"]
            ),
        ]

    @classmethod
    def generate_key(cls):
        return cls.KEY_PREFIX + secrets.token_urlsafe(32)

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

    @classmethod
    def create_key(cls, *, organization, name, created_by=None):
        """
        Create a key and return ``(api_key, raw_key)``.

        ``raw_key`` is never stored and must be shown to the user now.
        """

        raw_key = cls.generate_key()

        api_key = cls.objects.create(
            organization=organization,
            name=name,
            prefix=raw_key[: cls.DISPLAY_PREFIX_LENGTH],
            key_hash=cls.hash_key(raw_key),
            created_by=created_by,
        )

        return api_key, raw_key

    @property
    def is_active(self):
        return self.revoked_at is None

    def revoke(self, user=None):
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.save(update_fields=["revoked_at", "revoked_by"])

    def __str__(self):
        return f"{self.organization.name} - {self.name} ({self.prefix}...)"


class UsageRecord(models.Model):
    class ResourceType(models.TextChoices):
        API_REQUEST = "API_REQUEST", "API Request"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="usage_records",
    )

    resource = models.CharField(
        max_length=50,
        choices=ResourceType.choices,
        default=ResourceType.API_REQUEST,
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    # Set when the usage came from a product API call made with a key.
    # Null for manual records (dashboard / admin).
    api_key = models.ForeignKey(
        ApiKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usage_records",
    )

    endpoint = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["organization", "resource", "recorded_at"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.organization.name} - "
            f"{self.resource} - "
            f"{self.quantity}"
        )

class OverageCharge(models.Model):
    """
    Overage billed for one closed billing period of a subscription.

    One row per (subscription, period_start), so a period can never be
    billed twice (webhook retries, duplicate deliveries, manual command).
    """

    class Status(models.TextChoices):
        # Added to a specific draft Stripe invoice (renewal invoice).
        BILLED = "BILLED", "Billed"
        # Created as a pending Stripe invoice item; Stripe adds it to the
        # subscription's next invoice (used by the manual command).
        PENDING_NEXT_INVOICE = "PENDING_NEXT_INVOICE", "Pending next invoice"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="overage_charges",
    )

    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.CASCADE,
        related_name="overage_charges",
    )

    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    included_requests = models.PositiveIntegerField()
    used_requests = models.PositiveIntegerField()
    overage_requests = models.PositiveIntegerField()

    price_per_1000 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="usd",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
    )

    stripe_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    stripe_invoice_item_id = models.CharField(
        max_length=255,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-period_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "period_start"],
                name="unique_overage_charge_per_period",
            ),
        ]

    def __str__(self):
        return (
            f"{self.organization.name} - {self.overage_requests} extra "
            f"requests - {self.amount} {self.currency.upper()}"
        )


class UsageLimitOverride(models.Model):
    """
    A per-organization deal that replaces the plan's usage terms.

    Any field left empty falls back to the plan. Optional ``starts_at`` /
    ``ends_at`` make the deal apply only to a date window, so a change
    can be scheduled ahead (e.g. 100 requests this month, 80 from the
    1st of next month). Windows for one organization may not overlap.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="usage_limit_overrides",
    )

    api_request_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Requests included per billing period. Empty = plan's limit.",
    )

    overage_price_per_1000 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Price per 1,000 requests above the limit. "
            "Empty = plan's price. 0 = hard limit for this organization."
        ),
    )

    max_overage_requests = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Safety cap on overage per period. Empty = plan's cap.",
    )

    no_overage_cap = models.BooleanField(
        default=False,
        help_text="Remove the overage cap completely for this organization.",
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Applies from this moment. Empty = immediately.",
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Stops applying at this moment. Empty = no end.",
    )

    note = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Why this deal exists, e.g. 'Annual contract, signed 1 Nov'.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "-starts_at"]
        indexes = [
            models.Index(fields=["organization", "starts_at", "ends_at"]),
        ]

    def __str__(self):
        return f"Usage deal for {self.organization}"

    def is_active_at(self, moment):
        if self.starts_at and moment < self.starts_at:
            return False
        if self.ends_at and moment >= self.ends_at:
            return False
        return True

    @property
    def is_active(self):
        return self.is_active_at(timezone.now())

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must be after start."})

        if self.no_overage_cap and self.max_overage_requests is not None:
            raise ValidationError(
                {
                    "max_overage_requests": (
                        "Leave this empty when 'No overage cap' is ticked."
                    )
                }
            )

        if not self.organization_id:
            return

        # Two deals for the same org must not cover the same moment,
        # otherwise it would be unclear which limit applies.
        from datetime import datetime, timezone as dt_timezone

        far_past = datetime.min.replace(tzinfo=dt_timezone.utc)
        far_future = datetime.max.replace(tzinfo=dt_timezone.utc)
        start = self.starts_at or far_past
        end = self.ends_at or far_future

        others = UsageLimitOverride.objects.filter(
            organization_id=self.organization_id
        ).exclude(pk=self.pk)

        for other in others:
            other_start = other.starts_at or far_past
            other_end = other.ends_at or far_future
            if start < other_end and other_start < end:
                raise ValidationError(
                    "This date range overlaps another usage deal for "
                    "this organization. Set start/end dates so they "
                    "don't overlap."
                )


def active_override_for(organization_id, moment=None):
    """The organization's deal that applies at ``moment`` (or None)."""

    moment = moment or timezone.now()

    return (
        UsageLimitOverride.objects
        .filter(organization_id=organization_id)
        .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=moment))
        .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=moment))
        .order_by(models.F("starts_at").desc(nulls_last=True))
        .first()
    )
