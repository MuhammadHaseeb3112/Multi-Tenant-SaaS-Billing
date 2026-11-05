from rest_framework import serializers

from .models import ApiKey, OverageCharge, UsageRecord


class UsageRecordSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(
        required=True,
        min_value=1,
    )

    class Meta:
        model = UsageRecord
        fields = (
            "id",
            "organization",
            "resource",
            "quantity",
            "recorded_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "recorded_at",
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )

        return value


class ApiKeySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        default=None,
    )
    is_active = serializers.BooleanField(read_only=True)
    requests_this_period = serializers.IntegerField(
        read_only=True,
        default=0,
    )

    class Meta:
        model = ApiKey
        fields = (
            "id",
            "name",
            "prefix",
            "is_active",
            "created_by_email",
            "created_at",
            "last_used_at",
            "revoked_at",
            "requests_this_period",
        )
        read_only_fields = fields


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )


class TextAnalyzeSerializer(serializers.Serializer):
    MAX_LENGTH = 10000

    text = serializers.CharField(
        max_length=MAX_LENGTH,
        trim_whitespace=False,
    )

    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Text cannot be blank."
            )
        return value


class OverageChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OverageCharge
        fields = (
            "id",
            "period_start",
            "period_end",
            "included_requests",
            "used_requests",
            "overage_requests",
            "price_per_1000",
            "amount",
            "currency",
            "status",
            "stripe_invoice_id",
            "created_at",
        )
        read_only_fields = fields
