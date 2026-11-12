from rest_framework import serializers

from .models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "code",
            "name",
            "description",
            "monthly_price",
            "annual_price",
            "api_request_limit",
            "overage_price_per_1000",
            "max_overage_requests",
            "is_active",
        )
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(
        source="organization.id",
        read_only=True,
    )

    organization_name = serializers.CharField(
        source="organization.name",
        read_only=True,
    )

    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "organization_id",
            "organization_name",
            "plan",
            "status",
            "interval",
            "current_period_start",
            "current_period_end",
            "trial_start",
            "trial_end",
            "cancel_at_period_end",
            "canceled_at",
            # Dunning state, so the UI can warn before the downgrade.
            "payment_failed_at",
            "grace_period_end",
            "stripe_customer_id",
            "stripe_subscription_id",
            "created_at",
            "updated_at",
        )

        read_only_fields = fields



class CheckoutSerializer(serializers.Serializer):
    plan_code = serializers.ChoiceField(
        choices=["PRO", "ENTERPRISE"]
    )
    interval = serializers.ChoiceField(
        choices=["MONTHLY", "ANNUAL"]
    )


class ChangeSubscriptionSerializer(serializers.Serializer):
    plan_code = serializers.CharField(max_length=50)
    interval = serializers.ChoiceField(
        choices=Subscription.Interval.choices
    )

    def validate_plan_code(self, value):
        value = value.strip().upper()

        try:
            plan = Plan.objects.get(
                code=value,
                is_active=True,
            )
        except Plan.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid or inactive plan."
            )

        if plan.code == "FREE":
            raise serializers.ValidationError(
                "Free plan changes are handled through cancellation."
            )

        return plan.code