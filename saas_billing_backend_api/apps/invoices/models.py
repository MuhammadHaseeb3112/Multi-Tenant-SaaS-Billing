import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        PAID = "PAID", "Paid"
        VOID = "VOID", "Void"
        UNCOLLECTIBLE = "UNCOLLECTIBLE", "Uncollectible"

    class Currency(models.TextChoices):
        USD = "USD", "US Dollar"
        EUR = "EUR", "Euro"
        GBP = "GBP", "British Pound"
        PKR = "PKR", "Pakistani Rupee"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    invoice_number = models.CharField(
        max_length=50,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    issue_date = models.DateField()

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    billing_email = models.EmailField()

    # Emailing the invoice. Every send bumps payment_link_version, so
    # only the payment link in the newest email still works.
    sent_count = models.PositiveIntegerField(default=0)

    last_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    payment_link_version = models.PositiveIntegerField(default=0)

    stripe_invoice_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "invoice_number"],
                name="unique_invoice_number_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.organization.name}"


class InvoiceItem(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )

    description = models.CharField(
        max_length=255,
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description


class DunningAttempt(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    class AttemptType(models.TextChoices):
        FIRST_REMINDER = "FIRST_REMINDER", "First Reminder"
        SECOND_REMINDER = "SECOND_REMINDER", "Second Reminder"
        FINAL_REMINDER = "FINAL_REMINDER", "Final Reminder"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="dunning_attempts",
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="dunning_attempts",
    )

    attempt_type = models.CharField(
        max_length=30,
        choices=AttemptType.choices,
    )

    attempt_number = models.PositiveSmallIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    scheduled_at = models.DateTimeField()

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    failed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["attempt_number", "scheduled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "invoice",
                    "attempt_number",
                ],
                name="unique_dunning_attempt_per_invoice",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "status",
                    "scheduled_at",
                ]
            ),
            models.Index(
                fields=[
                    "invoice",
                    "attempt_number",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.invoice.invoice_number} - "
            f"{self.attempt_type} - "
            f"{self.status}"
        )

class Payment(models.Model):
    """
    A record of money actually received for an organization.

    Every way money can arrive creates exactly one Payment:
    - STRIPE subscription invoice paid  (key: stripe_invoice_id)
    - STRIPE one-off invoice checkout   (key: stripe_checkout_session_id)
    - MANUAL "mark as paid" by a finance user (bank transfer, cash...)

    The unique Stripe keys make webhook processing idempotent: a
    replayed event can never record the same money twice.
    """

    class Method(models.TextChoices):
        STRIPE = "STRIPE", "Stripe"
        MANUAL = "MANUAL", "Manual"

    class Status(models.TextChoices):
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially refunded"
        REFUNDED = "REFUNDED", "Refunded"

    # Statuses where (part of) the money is still kept. Revenue is
    # always computed as amount - amount_refunded over these.
    COLLECTED_STATUSES = (
        Status.SUCCEEDED,
        Status.PARTIALLY_REFUNDED,
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="payments",
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="USD",
    )

    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCEEDED,
    )

    stripe_invoice_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )

    stripe_checkout_session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    # Sum of SUCCEEDED refunds (Refund rows), kept in sync by
    # apps.invoices.refunds.recalculate_refunds().
    amount_refunded = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    paid_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-paid_at"]
        indexes = [
            models.Index(
                fields=["organization", "paid_at"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.organization.name} - {self.amount} "
            f"{self.currency} ({self.method})"
        )


class Refund(models.Model):
    """
    Money returned to a customer through Stripe (one row per Stripe
    refund, idempotent on stripe_refund_id). Only SUCCEEDED refunds
    reduce the payment's collected amount.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Null when the refund belongs to a payment this platform does not
    # know (e.g. a charge created outside the app). Kept for audit.
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="refunds",
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="refunds",
    )

    stripe_refund_id = models.CharField(
        max_length=255,
        unique=True,
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    stripe_charge_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    reason = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    refunded_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-refunded_at"]

    def __str__(self):
        return f"Refund {self.amount} {self.currency} ({self.status})"


class CreditNote(models.Model):
    """
    Mirror of a Stripe credit note (a correction to a finalized invoice:
    refund, customer balance credit or out-of-band). The money movement
    itself is tracked by Refund rows; this keeps the document trail.
    """

    class Status(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        VOID = "VOID", "Void"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="credit_notes",
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_notes",
    )

    stripe_credit_note_id = models.CharField(
        max_length=255,
        unique=True,
    )

    stripe_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    number = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    reason = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    issued_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Credit note {self.number or self.stripe_credit_note_id}"
