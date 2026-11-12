import stripe

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import create_audit_log
from apps.tenants.models import Organization
from apps.tenants.permissions import (
    IsOrganizationMember,
    IsOrganizationAdmin,
)

from .models import Plan, Subscription
from .serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    CheckoutSerializer,
    ChangeSubscriptionSerializer,
)
from .services import (
    SubscriptionChangeError,
    SubscriptionPaymentError,
    change_stripe_subscription,
)


class PlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True)

        serializer = PlanSerializer(
            plans,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class OrganizationSubscriptionView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        subscription = get_object_or_404(
            Subscription.objects.select_related(
                "organization",
                "plan",
            ),
            organization_id=organization_id,
        )

        serializer = SubscriptionSerializer(subscription)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class OrganizationCheckoutView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    # Local statuses that mean the organization still has a live
    # Stripe subscription. Checkout is blocked for these.
    BLOCKING_STATUSES = {
        Subscription.Status.ACTIVE,
        Subscription.Status.TRIALING,
        Subscription.Status.PAST_DUE,
        Subscription.Status.UNPAID,
    }

    def post(self, request, organization_id):
        serializer = CheckoutSerializer(
            data=request.data
        )
        serializer.is_valid(
            raise_exception=True
        )

        plan_code = serializer.validated_data["plan_code"]
        interval = serializer.validated_data["interval"]

        plan = get_object_or_404(
            Plan,
            code=plan_code,
            is_active=True,
        )

        if interval == Subscription.Interval.MONTHLY:
            price_id = plan.stripe_monthly_price_id
        else:
            price_id = plan.stripe_annual_price_id

        if not price_id:
            raise ValidationError(
                {
                    "detail": (
                        "This plan does not have "
                        "a Stripe price configured."
                    )
                }
            )

        organization = get_object_or_404(
            Organization,
            id=organization_id,
            is_active=True,
        )

        existing_subscription = Subscription.objects.filter(
            organization=organization
        ).first()

        # ---------------------------------------------------------
        # Prevent a second paid Stripe subscription
        # ---------------------------------------------------------
        #
        # An organization that is already paying must change its
        # plan through the subscription change endpoint. A new
        # Checkout session would create a SECOND Stripe subscription
        # and the old one would keep charging the customer.

        if (
            existing_subscription
            and existing_subscription.stripe_subscription_id
            and existing_subscription.status
            in self.BLOCKING_STATUSES
        ):
            return Response(
                {
                    "detail": (
                        "This organization already has a paid "
                        "subscription. Use the subscription change "
                        "endpoint to switch plans."
                    ),
                    "subscription_status": existing_subscription.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        metadata = {
            "organization_id": str(organization.id),
            "plan_code": plan.code,
            "interval": interval,
        }

        session_params = {
            "mode": "subscription",
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "success_url": settings.STRIPE_SUCCESS_URL,
            "cancel_url": settings.STRIPE_CANCEL_URL,
            # Lets the webhook find the organization even if
            # session metadata is missing.
            "client_reference_id": str(organization.id),
            "metadata": metadata,
            # Copied onto the Stripe subscription itself, so later
            # customer.subscription.* events can be mapped too.
            "subscription_data": {
                "metadata": metadata,
            },
        }

        # Reuse the organization's existing Stripe customer so we do
        # not create a new customer on every checkout.
        if (
            existing_subscription
            and existing_subscription.stripe_customer_id
        ):
            session_params["customer"] = (
                existing_subscription.stripe_customer_id
            )
        else:
            session_params["customer_email"] = request.user.email

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            checkout_session = stripe.checkout.Session.create(
                **session_params
            )

        except stripe.error.StripeError:
            return Response(
                {
                    "detail": (
                        "Stripe could not create "
                        "the checkout session."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # Audit log
        # ---------------------------------------------------------

        create_audit_log(
            organization=organization,
            user=request.user,
            action="CHECKOUT_SESSION_CREATED",
            resource_type="CheckoutSession",
            resource_id=checkout_session.id,
            description=(
                f"Stripe checkout session created for "
                f"{plan.name} ({interval})."
            ),
            metadata={
                "plan": plan.code,
                "interval": interval,
                "stripe_checkout_session_id": checkout_session.id,
            },
        )

        return Response(
            {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            },
            status=status.HTTP_201_CREATED,
        )


class OrganizationSubscriptionChangeView(APIView):
    """
    Change an organization's Stripe subscription plan or interval.

    Stripe is updated first, then webhooks synchronize
    the local subscription.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id):

        # ---------------------------------------------------------
        # Validate request data
        # ---------------------------------------------------------

        serializer = ChangeSubscriptionSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        plan_code = serializer.validated_data["plan_code"]
        interval = serializer.validated_data["interval"]

        # ---------------------------------------------------------
        # Get current subscription
        # ---------------------------------------------------------

        subscription = get_object_or_404(
            Subscription.objects.select_related(
                "organization",
                "plan",
            ),
            organization_id=organization_id,
        )

        # ---------------------------------------------------------
        # Get new plan
        # ---------------------------------------------------------

        new_plan = get_object_or_404(
            Plan,
            code=plan_code,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Prevent unnecessary changes
        # ---------------------------------------------------------

        if (
            subscription.plan_id == new_plan.id
            and subscription.interval == interval
        ):
            return Response(
                {
                    "detail": (
                        "The subscription is already using "
                        "this plan and interval."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Change Stripe subscription
        # ---------------------------------------------------------

        try:
            stripe_subscription = change_stripe_subscription(
                subscription=subscription,
                new_plan=new_plan,
                new_interval=interval,
            )

        except SubscriptionPaymentError as exc:
            create_audit_log(
                organization=subscription.organization,
                user=request.user,
                action="SUBSCRIPTION_UPGRADE_FAILED",
                resource_type="Subscription",
                resource_id=subscription.id,
                description=(
                    f"Upgrade to {new_plan.name} ({interval}) was not "
                    f"applied: the payment failed."
                ),
                metadata={
                    "plan": new_plan.code,
                    "interval": interval,
                },
            )

            return Response(
                {
                    "detail": str(exc),
                    "code": "payment_failed",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        except SubscriptionChangeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except stripe.error.CardError:
            return Response(
                {
                    "detail": (
                        "Your card was declined, so your plan was "
                        "not changed."
                    ),
                    "code": "payment_failed",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        except stripe.error.StripeError:
            return Response(
                {
                    "detail": (
                        "Stripe could not update "
                        "the subscription."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # Audit log
        # ---------------------------------------------------------

        create_audit_log(
            organization=subscription.organization,
            user=request.user,
            action="SUBSCRIPTION_CHANGED",
            resource_type="Subscription",
            resource_id=subscription.id,
            description=(
                f"Subscription change requested to "
                f"{new_plan.name} ({interval})."
            ),
            metadata={
                "plan": new_plan.code,
                "interval": interval,
                "stripe_subscription_id": (
                    subscription.stripe_subscription_id
                ),
            },
        )

        # ---------------------------------------------------------
        # Return response
        # ---------------------------------------------------------

        return Response(
            {
                "detail": (
                    "Subscription change submitted "
                    "successfully. Stripe webhook will "
                    "synchronize the local subscription."
                ),
                "subscription_id": (
                    stripe_subscription.get("id")
                ),
            },
            status=status.HTTP_200_OK,
        )


class OrganizationSubscriptionCancelView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id):

        subscription = get_object_or_404(
            Subscription.objects.select_related(
                "organization",
                "plan",
            ),
            organization_id=organization_id,
        )

        if not subscription.stripe_subscription_id:
            return Response(
                {
                    "detail": (
                        "This organization does not have "
                        "an active Stripe subscription."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subscription.status in {
            Subscription.Status.CANCELED,
            Subscription.Status.UNPAID,
        }:
            return Response(
                {
                    "detail": (
                        "This subscription cannot "
                        "be canceled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subscription.cancel_at_period_end:
            return Response(
                {
                    "detail": (
                        "Subscription is already scheduled "
                        "for cancellation."
                    ),
                    "subscription_id": (
                        subscription.stripe_subscription_id
                    ),
                },
                status=status.HTTP_200_OK,
            )

        # ---------------------------------------------------------
        # Configure Stripe
        # ---------------------------------------------------------

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            stripe_subscription = (
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                )
            )

        except stripe.error.StripeError:
            return Response(
                {
                    "detail": (
                        "Stripe could not schedule "
                        "the cancellation."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # Audit log
        # ---------------------------------------------------------

        create_audit_log(
            organization=subscription.organization,
            user=request.user,
            action="SUBSCRIPTION_CANCEL_SCHEDULED",
            resource_type="Subscription",
            resource_id=subscription.id,
            description=(
                "Subscription cancellation scheduled "
                "at the end of the current billing period."
            ),
            metadata={
                "cancel_at_period_end": True,
                "stripe_subscription_id": (
                    subscription.stripe_subscription_id
                ),
            },
        )

        return Response(
            {
                "detail": (
                    "Subscription cancellation scheduled "
                    "successfully. The subscription will remain "
                    "active until the current billing period ends."
                ),
                "subscription_id": stripe_subscription.id,
                "cancel_at_period_end": (
                    stripe_subscription.cancel_at_period_end
                ),
            },
            status=status.HTTP_200_OK,
        )


class ResumeSubscriptionView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id):

        subscription = get_object_or_404(
            Subscription.objects.select_related(
                "organization",
                "plan",
            ),
            organization_id=organization_id,
        )

        if not subscription.stripe_subscription_id:
            return Response(
                {
                    "detail": (
                        "This subscription is not "
                        "connected to Stripe."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subscription.status != Subscription.Status.ACTIVE:
            return Response(
                {
                    "detail": (
                        "Only an active subscription "
                        "can be resumed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not subscription.cancel_at_period_end:
            return Response(
                {
                    "detail": (
                        "This subscription is not scheduled "
                        "for cancellation."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Resume Stripe subscription
        # ---------------------------------------------------------

        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY

            stripe_subscription = (
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                )
            )

        except stripe.error.StripeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Audit log
        # ---------------------------------------------------------

        create_audit_log(
            organization=subscription.organization,
            user=request.user,
            action="SUBSCRIPTION_RESUMED",
            resource_type="Subscription",
            resource_id=subscription.id,
            description="Subscription resumed successfully.",
            metadata={
                "cancel_at_period_end": False,
                "stripe_subscription_id": (
                    subscription.stripe_subscription_id
                ),
            },
        )

        # ---------------------------------------------------------
        # Return response
        # ---------------------------------------------------------

        return Response(
            {
                "detail": (
                    "Subscription resumed successfully. "
                    "The Stripe webhook will synchronize "
                    "the local subscription."
                ),
                "subscription_id": stripe_subscription.id,
                "cancel_at_period_end": (
                    stripe_subscription.cancel_at_period_end
                ),
            },
            status=status.HTTP_200_OK,
        )

class BillingPortalView(APIView):
    """
    Open the Stripe Customer Portal for the organization, where an
    admin can update the card on file (for example after a failed
    payment). Plan changes stay in this app; the portal is only for
    payment details and billing info.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id):
        subscription = get_object_or_404(
            Subscription.objects.select_related("organization"),
            organization_id=organization_id,
            organization__is_active=True,
        )

        if not subscription.stripe_customer_id:
            return Response(
                {
                    "detail": (
                        "This organization has no Stripe billing "
                        "account yet. Subscribe to a paid plan first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return_url = (
            settings.FRONTEND_URL.rstrip("/") + "/subscriptions"
        )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=return_url,
            )

        except stripe.error.StripeError:
            return Response(
                {
                    "detail": (
                        "Stripe could not open the billing portal."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        create_audit_log(
            organization=subscription.organization,
            user=request.user,
            action="BILLING_PORTAL_OPENED",
            resource_type="Subscription",
            resource_id=subscription.id,
            description="Stripe billing portal opened.",
            metadata={
                "stripe_customer_id": subscription.stripe_customer_id,
            },
        )

        return Response(
            {"url": portal_session.url},
            status=status.HTTP_201_CREATED,
        )
