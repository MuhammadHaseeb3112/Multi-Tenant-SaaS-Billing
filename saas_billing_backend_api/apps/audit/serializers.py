from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(
        source="user.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "organization",
            "user",
            "user_email",
            "action",
            "resource_type",
            "resource_id",
            "description",
            "metadata",
            "created_at",
        )
        read_only_fields = fields