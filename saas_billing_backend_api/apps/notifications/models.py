import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        PAYMENT_SUCCESS = "PAYMENT_SUCCESS", "Payment Successful"
        PAYMENT_FAILED = "PAYMENT_FAILED", "Payment Failed"
        SUBSCRIPTION_UPDATED = "SUBSCRIPTION_UPDATED", "Subscription Updated"
        SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED", "Subscription Cancelled"
        SUBSCRIPTION_RESUMED = "SUBSCRIPTION_RESUMED", "Subscription Resumed"
        USAGE_WARNING = "USAGE_WARNING", "Usage Warning"
        USAGE_LIMIT_REACHED = "USAGE_LIMIT_REACHED", "Usage Limit Reached"
        INVOICE_CREATED = "INVOICE_CREATED", "Invoice Created"
        INVOICE_OVERDUE = "INVOICE_OVERDUE", "Invoice Overdue"
        INVITATION_RECEIVED = "INVITATION_RECEIVED", "Invitation Received"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read", "created_at"]
            ),
            models.Index(
                fields=["organization", "created_at"]
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"