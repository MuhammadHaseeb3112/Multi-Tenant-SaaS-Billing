from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import create_audit_log
from apps.billing.models import Subscription
from apps.tenants.models import Organization
from apps.tenants.permissions import (
    IsOrganizationAdmin,
    IsOrganizationMember,
)

from .authentication import ApiKeyAuthentication, HasApiKey
from .models import ApiKey, OverageCharge
from .serializers import (
    ApiKeyCreateSerializer,
    ApiKeySerializer,
    OverageChargeSerializer,
    TextAnalyzeSerializer,
    UsageRecordSerializer,
)
from .services import (
    NoSubscription,
    UsageLimitExceeded,
    get_current_usage,  # noqa: F401  (re-exported; used by tests)
    get_usage_period,
    get_usage_summary,
    record_usage,
)
from .text_insights import analyze_text


MAX_ACTIVE_API_KEYS = 10


def limit_exceeded_body(exc):
    body = {
        "detail": "Usage limit exceeded.",
        "used": exc.summary.used,
        "requested": exc.requested,
        "limit": exc.summary.limit,
        "remaining": exc.summary.remaining,
    }

    if exc.summary.overage_enabled:
        body["overage_requests"] = exc.summary.overage_requests
        body["max_overage_requests"] = exc.summary.max_overage_requests

    return body


# =============================================================================
# Dashboard API (JWT)
# =============================================================================


class RecordUsageView(APIView):
    """
    Manual usage record from the dashboard.

    Real usage is now recorded by the product API (``/api/v1/``) when
    it is called with an API key. This endpoint stays for manual
    adjustments/testing and is limited to OWNER/ADMIN (previously any
    member could inflate the organization's usage). Each call is audited.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id):
        serializer = UsageRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data["quantity"]

        try:
            usage_record, _summary = record_usage(
                organization_id=organization_id,
                quantity=quantity,
                endpoint="manual",
            )
        except NoSubscription:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except UsageLimitExceeded as exc:
            return Response(
                limit_exceeded_body(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_audit_log(
            organization=usage_record.organization,
            user=request.user,
            action="USAGE_RECORDED_MANUALLY",
            resource_type="UsageRecord",
            resource_id=usage_record.id,
            description=f"Manually recorded {quantity} API request(s).",
            metadata={"quantity": quantity},
        )

        return Response(
            UsageRecordSerializer(usage_record).data,
            status=status.HTTP_201_CREATED,
        )


class UsageSummaryView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        subscription = get_object_or_404(
            Subscription.objects.select_related("plan"),
            organization_id=organization_id,
        )

        return Response(
            get_usage_summary(subscription).as_dict(),
            status=status.HTTP_200_OK,
        )


class OverageChargeListView(APIView):
    """
    Overage billed in past periods (finance view of usage-based charges).
    Any member can see it, like the usage summary.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        charges = OverageCharge.objects.filter(
            organization_id=organization_id
        )

        return Response(
            OverageChargeSerializer(charges, many=True).data,
            status=status.HTTP_200_OK,
        )


class ApiKeyListCreateView(APIView):
    """
    GET  -> list the organization's keys (active and revoked).
    POST -> create a key; the plaintext key is in the response ONCE.

    OWNER/ADMIN only.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def get(self, request, organization_id):
        keys = ApiKey.objects.filter(
            organization_id=organization_id
        ).select_related("created_by")

        subscription = Subscription.objects.filter(
            organization_id=organization_id
        ).first()

        if subscription:
            start, end = get_usage_period(subscription)
            period_filter = Q(usage_records__recorded_at__gte=start)
            if end:
                period_filter &= Q(usage_records__recorded_at__lt=end)

            keys = keys.annotate(
                requests_this_period=Coalesce(
                    Sum("usage_records__quantity", filter=period_filter),
                    Value(0),
                )
            )

        return Response(
            ApiKeySerializer(keys, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, organization_id):
        organization = get_object_or_404(
            Organization, id=organization_id
        )

        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_count = ApiKey.objects.filter(
            organization=organization,
            revoked_at__isnull=True,
        ).count()

        if active_count >= MAX_ACTIVE_API_KEYS:
            return Response(
                {
                    "detail": (
                        f"An organization can have at most "
                        f"{MAX_ACTIVE_API_KEYS} active API keys. "
                        f"Revoke an unused key first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key, raw_key = ApiKey.create_key(
            organization=organization,
            name=serializer.validated_data["name"],
            created_by=request.user,
        )

        create_audit_log(
            organization=organization,
            user=request.user,
            action="API_KEY_CREATED",
            resource_type="ApiKey",
            resource_id=api_key.id,
            description=f"API key '{api_key.name}' created.",
            metadata={"prefix": api_key.prefix},
        )

        data = ApiKeySerializer(api_key).data
        data["key"] = raw_key

        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeView(APIView):
    """
    DELETE -> revoke a key (soft: the row and its usage history stay).
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def delete(self, request, organization_id, key_id):
        api_key = get_object_or_404(
            ApiKey,
            id=key_id,
            organization_id=organization_id,
        )

        if api_key.is_active:
            api_key.revoke(user=request.user)

            create_audit_log(
                organization=api_key.organization,
                user=request.user,
                action="API_KEY_REVOKED",
                resource_type="ApiKey",
                resource_id=api_key.id,
                description=f"API key '{api_key.name}' revoked.",
                metadata={"prefix": api_key.prefix},
            )

        return Response(
            ApiKeySerializer(api_key).data,
            status=status.HTTP_200_OK,
        )


# =============================================================================
# Product API (API key) - /api/v1/
# =============================================================================


class ProductAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKey]

    @staticmethod
    def add_limit_headers(response, summary):
        response["X-RateLimit-Limit"] = str(summary.limit)
        response["X-RateLimit-Remaining"] = str(summary.remaining)
        if summary.overage_enabled:
            response["X-Overage-Requests"] = str(summary.overage_requests)
        if summary.period_end:
            response["X-RateLimit-Reset"] = str(
                int(summary.period_end.timestamp())
            )
        return response


class TextAnalyzeView(ProductAPIView):
    """
    POST /api/v1/text/analyze/   {"text": "..."}

    Metered: each successful call records 1 API_REQUEST for the key's
    organization. Invalid input is rejected before metering (not billed).
    Over the plan limit -> 429, unless the plan allows paid overage
    (then allowed up to the plan's overage cap, billed at period end).
    """

    endpoint_name = "text.analyze"

    def post(self, request):
        serializer = TextAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_key = request.auth

        try:
            _record, summary = record_usage(
                organization_id=api_key.organization_id,
                quantity=1,
                api_key=api_key,
                endpoint=self.endpoint_name,
            )
        except NoSubscription:
            return Response(
                {"detail": "Organization has no subscription."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except UsageLimitExceeded as exc:
            body = limit_exceeded_body(exc)
            body["detail"] = (
                "Overage cap reached for this billing period."
                if exc.summary.overage_enabled
                else "API request limit reached. Upgrade your plan "
                "or wait for the next billing period."
            )
            response = Response(
                body,
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            return self.add_limit_headers(response, exc.summary)

        result = analyze_text(serializer.validated_data["text"])

        return self.add_limit_headers(
            Response(result, status=status.HTTP_200_OK),
            summary,
        )


class ProductUsageView(ProductAPIView):
    """
    GET /api/v1/usage/  - current usage of the key's organization.
    Not metered.
    """

    def get(self, request):
        subscription = (
            Subscription.objects
            .select_related("plan")
            .filter(organization_id=request.auth.organization_id)
            .first()
        )

        if subscription is None:
            return Response(
                {"detail": "Organization has no subscription."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        summary = get_usage_summary(subscription)

        return self.add_limit_headers(
            Response(summary.as_dict(), status=status.HTTP_200_OK),
            summary,
        )
