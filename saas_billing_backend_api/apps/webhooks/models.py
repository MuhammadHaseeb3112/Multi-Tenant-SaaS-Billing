import uuid

from django.db import models


class WebhookEvent(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )

    event_type = models.CharField(
        max_length=255,
    )

    processed = models.BooleanField(
        default=False,
    )

    payload = models.JSONField(
        default=dict,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.stripe_event_id}"