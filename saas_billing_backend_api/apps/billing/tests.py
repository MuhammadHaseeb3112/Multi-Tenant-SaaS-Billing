from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.tenants.models import Membership, Organization

from .models import Plan, Subscription
from .services import SubscriptionChangeError, change_stripe_subscription
from .tasks import process_expired_grace_periods


class BillingTestBase(APITestCase):
    """
    Shared test setup for Billing tests.
    """

    def setUp(self):
        # ---------------------------------------------------------
        # Plans
        # ---------------------------------------------------------

        self.free_plan = Plan.objects.create(
            code="FREE",
            name="Free",
            description="Free plan",
            monthly_price=Decimal("0.00"),
            annual_price=Decimal("0.00"),
            api_request_limit=1000,
            is_active=True,
        )

        self.pro_plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            description="Pro plan",
            monthly_price=Decimal("29.00"),
            annual_price=Decimal("290.00"),
            api_request_limit=10000,
            stripe_product_id="prod_test_pro",
            stripe_monthly_price_id="price_test_pro_monthly",
            stripe_annual_price_id="price_test_pro_annual",
            is_active=True,
        )

        self.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            description="Enterprise plan",
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            api_request_limit=100000,
            stripe_product_id="prod_test_enterprise",
            stripe_monthly_price_id="price_test_enterprise_monthly",
            stripe_annual_price_id="price_test_enterprise_annual",
            is_active=True,
        )

        self.inactive_plan = Plan.objects.create(
            code="OLD",
            name="Old Plan",
            description="Inactive plan",
            monthly_price=Decimal("10.00"),
            annual_price=Decimal("100.00"),
            api_request_limit=500,
            is_active=False,
        )

        # ---------------------------------------------------------
        # Organization 1
        # ---------------------------------------------------------

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="TestPassword123",
            first_name="Owner",
            last_name="User",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123",
            first_name="Admin",
            last_name="User",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123",
            first_name="Member",
            last_name="User",
        )

        self.organization = Organization.objects.create(
            name="Acme Corporation",
            slug="acme-corporation",
            billing_email="billing@acme.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        )

        Membership.objects.create(
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
            is_active=True,
        )

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            stripe_customer_id="cus_test_acme",
            stripe_subscription_id="sub_test_acme",
        )

        # ---------------------------------------------------------
        # Organization 2
        # ---------------------------------------------------------

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123",
            first_name="Other",
            last_name="Owner",
        )

        self.other_organization = Organization.objects.create(
            name="Other Corporation",
            slug="other-corporation",
            billing_email="billing@other.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        self.other_subscription = Subscription.objects.create(
            organization=self.other_organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            stripe_customer_id="cus_test_other",
            stripe_subscription_id="sub_test_other",
        )

    # -------------------------------------------------------------
    # Authentication helper
    # -------------------------------------------------------------

    def authenticate(self, user):
        response = self.client.post(
            reverse("login"),
            {
                "email": user.email,
                "password": "TestPassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {response.data['tokens']['access']}"
            )
        )

    def clear_auth(self):
        self.client.credentials()

    # -------------------------------------------------------------
    # URL helpers
    # -------------------------------------------------------------

    def subscription_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "organization-subscription",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def checkout_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "organization-checkout",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def change_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "organization-subscription-change",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def cancel_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "organization-subscription-cancel",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def resume_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "subscription-resume",
            kwargs={
                "organization_id": organization.id,
            },
        )


class PlanListTests(BillingTestBase):
    """
    Tests for GET /api/billing/plans/
    """

    def test_plans_endpoint_is_public(self):
        self.clear_auth()

        response = self.client.get(
            reverse("billing-plans")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_only_active_plans_are_returned(self):
        response = self.client.get(
            reverse("billing-plans")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        codes = {
            item["code"]
            for item in response.data
        }

        self.assertIn("FREE", codes)
        self.assertIn("PRO", codes)
        self.assertIn("ENTERPRISE", codes)
        self.assertNotIn("OLD", codes)

    def test_plan_serializer_returns_expected_fields(self):
        response = self.client.get(
            reverse("billing-plans")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        pro = next(
            item
            for item in response.data
            if item["code"] == "PRO"
        )

        self.assertEqual(pro["name"], "Pro")
        self.assertEqual(
            Decimal(str(pro["monthly_price"])),
            Decimal("29.00"),
        )
        self.assertEqual(
            Decimal(str(pro["annual_price"])),
            Decimal("290.00"),
        )
        self.assertEqual(
            pro["api_request_limit"],
            10000,
        )
        self.assertTrue(pro["is_active"])


class OrganizationSubscriptionTests(BillingTestBase):
    """
    Tests for GET organization subscription.
    """

    def test_member_can_view_subscription(self):
        self.authenticate(self.member)

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["organization_id"],
            str(self.organization.id),
        )

        self.assertEqual(
            response.data["organization_name"],
            self.organization.name,
        )

        self.assertEqual(
            response.data["plan"]["code"],
            "PRO",
        )

        self.assertEqual(
            response.data["status"],
            Subscription.Status.ACTIVE,
        )

    def test_admin_can_view_subscription(self):
        self.authenticate(self.admin)

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_owner_can_view_subscription(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_unauthenticated_user_cannot_view_subscription(self):
        self.clear_auth()

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_cross_tenant_subscription_access_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.subscription_url(
                self.organization
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_membership_cannot_view_subscription(self):
        Membership.objects.filter(
            user=self.member,
            organization=self.organization,
        ).update(
            is_active=False
        )

        self.authenticate(self.member)

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_organization_cannot_be_accessed(self):
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.authenticate(self.owner)

        response = self.client.get(
            self.subscription_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class CheckoutTests(BillingTestBase):
    """
    Tests for Stripe Checkout Session creation.

    Checkout is only for organizations without a live paid Stripe
    subscription (normally a new organization on the FREE plan).
    """

    def setUp(self):
        super().setUp()

        # Realistic starting point: organization on FREE, never paid.
        self.subscription.plan = self.free_plan
        self.subscription.stripe_customer_id = None
        self.subscription.stripe_subscription_id = None
        self.subscription.save()

    def make_paid(self, status=Subscription.Status.ACTIVE):
        self.subscription.plan = self.pro_plan
        self.subscription.status = status
        self.subscription.stripe_customer_id = "cus_test_acme"
        self.subscription.stripe_subscription_id = "sub_test_acme"
        self.subscription.save()

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_checkout_blocked_when_paid_subscription_exists(
        self,
        mock_create,
    ):
        self.make_paid()
        self.authenticate(self.owner)

        response = self.client.post(
            self.checkout_url(),
            {"plan_code": "ENTERPRISE", "interval": "ANNUAL"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        mock_create.assert_not_called()

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_checkout_blocked_when_subscription_past_due(
        self,
        mock_create,
    ):
        self.make_paid(status=Subscription.Status.PAST_DUE)
        self.authenticate(self.owner)

        response = self.client.post(
            self.checkout_url(),
            {"plan_code": "PRO", "interval": "MONTHLY"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        mock_create.assert_not_called()

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_canceled_subscription_can_checkout_and_reuses_customer(
        self,
        mock_create,
    ):
        self.make_paid(status=Subscription.Status.CANCELED)
        self.authenticate(self.owner)

        mock_create.return_value = SimpleNamespace(
            id="cs_test_resubscribe",
            url="https://checkout.stripe.com/resubscribe",
        )

        response = self.client.post(
            self.checkout_url(),
            {"plan_code": "PRO", "interval": "MONTHLY"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["customer"], "cus_test_acme")
        self.assertNotIn("customer_email", kwargs)

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_new_customer_checkout_sends_org_references(
        self,
        mock_create,
    ):
        self.authenticate(self.owner)

        mock_create.return_value = SimpleNamespace(
            id="cs_test_refs",
            url="https://checkout.stripe.com/refs",
        )

        response = self.client.post(
            self.checkout_url(),
            {"plan_code": "PRO", "interval": "MONTHLY"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        kwargs = mock_create.call_args.kwargs
        org_id = str(self.organization.id)

        self.assertEqual(kwargs["customer_email"], self.owner.email)
        self.assertNotIn("customer", kwargs)
        self.assertEqual(kwargs["client_reference_id"], org_id)
        self.assertEqual(kwargs["metadata"]["organization_id"], org_id)
        self.assertEqual(
            kwargs["subscription_data"]["metadata"]["organization_id"],
            org_id,
        )

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_stripe_error_returns_502_without_audit_log(
        self,
        mock_create,
    ):
        import stripe as stripe_module

        self.authenticate(self.owner)

        mock_create.side_effect = stripe_module.error.APIConnectionError(
            "Stripe unreachable"
        )

        response = self.client.post(
            self.checkout_url(),
            {"plan_code": "PRO", "interval": "MONTHLY"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )
        self.assertFalse(
            AuditLog.objects.filter(
                action="CHECKOUT_SESSION_CREATED"
            ).exists()
        )

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_admin_can_create_checkout_session(
        self,
        mock_create,
    ):
        self.authenticate(self.admin)

        mock_create.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.com/test",
        )

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "PRO",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["session_id"],
            "cs_test_123",
        )

        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.stripe.com/test",
        )

        mock_create.assert_called_once()

        audit_exists = AuditLog.objects.filter(
            organization=self.organization,
            user=self.admin,
            action="CHECKOUT_SESSION_CREATED",
        ).exists()

        self.assertTrue(audit_exists)

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_owner_can_create_checkout_session(
        self,
        mock_create,
    ):
        self.authenticate(self.owner)

        mock_create.return_value = SimpleNamespace(
            id="cs_test_owner",
            url="https://checkout.stripe.com/owner",
        )

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "ENTERPRISE",
                "interval": "ANNUAL",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_member_cannot_create_checkout_session(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "PRO",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_checkout(self):
        self.clear_auth()

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "PRO",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_annual_checkout_uses_annual_price(
        self,
        mock_create,
    ):
        self.authenticate(self.owner)

        mock_create.return_value = SimpleNamespace(
            id="cs_test_annual",
            url="https://checkout.stripe.com/annual",
        )

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "PRO",
                "interval": "ANNUAL",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["line_items"][0]["price"],
            self.pro_plan.stripe_annual_price_id,
        )

    @patch("apps.billing.views.stripe.checkout.Session.create")
    def test_checkout_requires_configured_stripe_price(
        self,
        mock_create,
    ):
        self.pro_plan.stripe_monthly_price_id = None
        self.pro_plan.save(
            update_fields=["stripe_monthly_price_id"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.checkout_url(),
            {
                "plan_code": "PRO",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        mock_create.assert_not_called()


class SubscriptionChangeSerializerTests(BillingTestBase):
    """
    Tests for ChangeSubscriptionSerializer validation.
    """

    def test_valid_plan_and_interval_are_accepted(self):
        from .serializers import ChangeSubscriptionSerializer

        serializer = ChangeSubscriptionSerializer(
            data={
                "plan_code": "pro",
                "interval": "MONTHLY",
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["plan_code"],
            "PRO",
        )

    def test_plan_code_is_normalized(self):
        from .serializers import ChangeSubscriptionSerializer

        serializer = ChangeSubscriptionSerializer(
            data={
                "plan_code": "  enterprise  ",
                "interval": "ANNUAL",
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["plan_code"],
            "ENTERPRISE",
        )

    def test_free_plan_change_is_rejected(self):
        from .serializers import ChangeSubscriptionSerializer

        serializer = ChangeSubscriptionSerializer(
            data={
                "plan_code": "FREE",
                "interval": "MONTHLY",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Free plan changes are handled through cancellation.",
            str(serializer.errors),
        )

    def test_invalid_plan_is_rejected(self):
        from .serializers import ChangeSubscriptionSerializer

        serializer = ChangeSubscriptionSerializer(
            data={
                "plan_code": "DOES_NOT_EXIST",
                "interval": "MONTHLY",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Invalid or inactive plan.",
            str(serializer.errors),
        )

    def test_inactive_plan_is_rejected(self):
        from .serializers import ChangeSubscriptionSerializer

        serializer = ChangeSubscriptionSerializer(
            data={
                "plan_code": "OLD",
                "interval": "MONTHLY",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Invalid or inactive plan.",
            str(serializer.errors),
        )


class SubscriptionChangeServiceTests(BillingTestBase):
    """
    Direct tests for Stripe subscription change service.
    """

    @patch("apps.billing.services.stripe.Subscription.retrieve")
    @patch("apps.billing.services.stripe.Subscription.modify")
    def test_change_stripe_subscription_updates_price(
        self,
        mock_modify,
        mock_retrieve,
    ):
        stripe_subscription = SimpleNamespace(
            id="sub_test_acme",
            items={
                "data": [
                    {
                        "id": "si_test_item",
                        "price": {
                            "id": self.pro_plan.stripe_monthly_price_id,
                        },
                    }
                ]
            },
        )

        updated_subscription = SimpleNamespace(
            id="sub_test_acme",
            to_dict=lambda: {
                "id": "sub_test_acme",
                "status": "active",
            },
        )

        mock_retrieve.return_value.to_dict.return_value = (
            stripe_subscription.__dict__
        )

        mock_modify.return_value = updated_subscription

        result = change_stripe_subscription(
            subscription=self.subscription,
            new_plan=self.enterprise_plan,
            new_interval=Subscription.Interval.ANNUAL,
        )

        self.assertEqual(
            result["id"],
            "sub_test_acme",
        )

        mock_modify.assert_called_once()

        kwargs = mock_modify.call_args.kwargs

        self.assertEqual(
            kwargs["items"][0]["price"],
            self.enterprise_plan.stripe_annual_price_id,
        )

        self.assertEqual(
            kwargs["proration_behavior"],
            "create_prorations",
        )

    def test_change_requires_stripe_subscription_id(self):
        subscription = self.subscription

        subscription.stripe_subscription_id = None
        subscription.save(
            update_fields=["stripe_subscription_id"]
        )

        with self.assertRaises(SubscriptionChangeError) as context:
            change_stripe_subscription(
                subscription=subscription,
                new_plan=self.enterprise_plan,
                new_interval=Subscription.Interval.MONTHLY,
            )

        self.assertIn(
            "does not have an active Stripe subscription",
            str(context.exception),
        )

    def test_change_requires_stripe_price(self):
        self.enterprise_plan.stripe_monthly_price_id = None
        self.enterprise_plan.save(
            update_fields=["stripe_monthly_price_id"]
        )

        with self.assertRaises(SubscriptionChangeError) as context:
            change_stripe_subscription(
                subscription=self.subscription,
                new_plan=self.enterprise_plan,
                new_interval=Subscription.Interval.MONTHLY,
            )

        self.assertIn(
            "No Stripe price is configured",
            str(context.exception),
        )

    @patch("apps.billing.services.stripe.Subscription.retrieve")
    def test_change_rejects_subscription_without_items(
        self,
        mock_retrieve,
    ):
        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_test_acme",
            "items": {
                "data": []
            },
        }

        with self.assertRaises(SubscriptionChangeError) as context:
            change_stripe_subscription(
                subscription=self.subscription,
                new_plan=self.enterprise_plan,
                new_interval=Subscription.Interval.MONTHLY,
            )

        self.assertIn(
            "has no subscription items",
            str(context.exception),
        )

    @patch("apps.billing.services.stripe.Subscription.retrieve")
    def test_change_rejects_same_price(
        self,
        mock_retrieve,
    ):
        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_test_acme",
            "items": {
                "data": [
                    {
                        "id": "si_test",
                        "price": {
                            "id": self.pro_plan.stripe_monthly_price_id
                        },
                    }
                ]
            },
        }

        with self.assertRaises(SubscriptionChangeError) as context:
            change_stripe_subscription(
                subscription=self.subscription,
                new_plan=self.pro_plan,
                new_interval=Subscription.Interval.MONTHLY,
            )

        self.assertIn(
            "already using this plan and interval",
            str(context.exception),
        )


class SubscriptionChangeAPITests(BillingTestBase):
    """
    Tests for POST subscription/change/.
    """

    @patch("apps.billing.views.change_stripe_subscription")
    def test_admin_can_change_subscription(
        self,
        mock_change,
    ):
        self.authenticate(self.admin)

        mock_change.return_value = {
            "id": "sub_test_acme"
        }

        response = self.client.post(
            self.change_url(),
            {
                "plan_code": "ENTERPRISE",
                "interval": "ANNUAL",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["subscription_id"],
            "sub_test_acme",
        )

        mock_change.assert_called_once()

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                user=self.admin,
                action="SUBSCRIPTION_CHANGED",
            ).exists()
        )

    def test_member_cannot_change_subscription(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.change_url(),
            {
                "plan_code": "ENTERPRISE",
                "interval": "ANNUAL",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_same_plan_and_interval_are_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.change_url(),
            {
                "plan_code": "PRO",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "already using this plan",
            response.data["detail"],
        )

    @patch("apps.billing.views.change_stripe_subscription")
    def test_stripe_change_error_returns_400(
        self,
        mock_change,
    ):
        self.authenticate(self.owner)

        mock_change.side_effect = SubscriptionChangeError(
            "This organization does not have an active Stripe subscription."
        )

        response = self.client.post(
            self.change_url(),
            {
                "plan_code": "ENTERPRISE",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cross_tenant_subscription_change_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.change_url(self.organization),
            {
                "plan_code": "ENTERPRISE",
                "interval": "MONTHLY",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class SubscriptionCancelTests(BillingTestBase):
    """
    Tests for subscription cancellation.
    """

    @patch("apps.billing.views.stripe.Subscription.modify")
    def test_admin_can_schedule_cancellation(
        self,
        mock_modify,
    ):
        self.authenticate(self.admin)

        mock_modify.return_value = SimpleNamespace(
            id="sub_test_acme",
            cancel_at_period_end=True,
        )

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            response.data["cancel_at_period_end"]
        )

        mock_modify.assert_called_once()

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                user=self.admin,
                action="SUBSCRIPTION_CANCEL_SCHEDULED",
            ).exists()
        )

    def test_member_cannot_cancel_subscription(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cancel_requires_stripe_subscription(self):
        self.subscription.stripe_subscription_id = None
        self.subscription.save(
            update_fields=["stripe_subscription_id"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "does not have an active Stripe subscription",
            response.data["detail"],
        )

    def test_canceled_subscription_cannot_be_canceled_again(self):
        self.subscription.status = Subscription.Status.CANCELED
        self.subscription.save(
            update_fields=["status"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unpaid_subscription_cannot_be_canceled(self):
        self.subscription.status = Subscription.Status.UNPAID
        self.subscription.save(
            update_fields=["status"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_already_scheduled_cancellation_returns_200(
        self,
    ):
        self.subscription.cancel_at_period_end = True
        self.subscription.save(
            update_fields=["cancel_at_period_end"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.cancel_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "already scheduled",
            response.data["detail"],
        )


class SubscriptionResumeTests(BillingTestBase):
    """
    Tests for subscription resume.
    """

    @patch("apps.billing.views.stripe.Subscription.modify")
    def test_admin_can_resume_subscription(
        self,
        mock_modify,
    ):
        self.subscription.cancel_at_period_end = True
        self.subscription.save(
            update_fields=["cancel_at_period_end"]
        )

        self.authenticate(self.admin)

        mock_modify.return_value = SimpleNamespace(
            id="sub_test_acme",
            cancel_at_period_end=False,
        )

        response = self.client.post(
            self.resume_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertFalse(
            response.data["cancel_at_period_end"]
        )

        mock_modify.assert_called_once()

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                user=self.admin,
                action="SUBSCRIPTION_RESUMED",
            ).exists()
        )

    def test_member_cannot_resume_subscription(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.resume_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_resume_requires_stripe_subscription(self):
        self.subscription.stripe_subscription_id = None
        self.subscription.save(
            update_fields=["stripe_subscription_id"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.resume_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_only_active_subscription_can_be_resumed(self):
        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.cancel_at_period_end = True

        self.subscription.save(
            update_fields=[
                "status",
                "cancel_at_period_end",
            ]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.resume_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "Only an active subscription",
            response.data["detail"],
        )

    def test_resume_requires_cancellation_schedule(self):
        self.subscription.cancel_at_period_end = False
        self.subscription.save(
            update_fields=["cancel_at_period_end"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.resume_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "not scheduled for cancellation",
            response.data["detail"],
        )

    def test_cross_tenant_resume_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.resume_url(self.organization)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class GracePeriodTaskTests(BillingTestBase):
    """
    Tests for process_expired_grace_periods Celery task.

    Stripe is mocked for every test: the task must never call the real
    Stripe API from the test suite.
    """

    def setUp(self):
        super().setUp()

        patcher = patch(
            "apps.billing.tasks.stripe.Subscription.cancel"
        )
        self.mock_stripe_cancel = patcher.start()
        self.addCleanup(patcher.stop)

    def expire_grace_period(self, subscription=None):
        subscription = subscription or self.subscription
        subscription.status = Subscription.Status.PAST_DUE
        subscription.payment_failed_at = (
            timezone.now() - timedelta(days=8)
        )
        subscription.payment_retry_count = 3
        subscription.grace_period_end = (
            timezone.now() - timedelta(hours=1)
        )
        subscription.save()

    def test_expired_grace_period_cancels_stripe_subscription(self):
        self.expire_grace_period()

        result = process_expired_grace_periods()

        self.assertEqual(result, 1)
        self.mock_stripe_cancel.assert_called_once_with("sub_test_acme")

        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.plan, self.free_plan)
        self.assertIsNone(self.subscription.stripe_subscription_id)
        # Customer is kept so a later checkout reuses it.
        self.assertEqual(
            self.subscription.stripe_customer_id,
            "cus_test_acme",
        )
        self.assertIsNotNone(self.subscription.canceled_at)

    def test_stripe_failure_leaves_subscription_past_due(self):
        import stripe as stripe_module

        self.expire_grace_period()

        self.mock_stripe_cancel.side_effect = (
            stripe_module.error.APIConnectionError("Stripe unreachable")
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 0)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.PAST_DUE,
        )
        self.assertEqual(self.subscription.plan, self.pro_plan)
        self.assertEqual(
            self.subscription.stripe_subscription_id,
            "sub_test_acme",
        )

    def test_already_canceled_in_stripe_still_downgrades(self):
        import stripe as stripe_module

        self.expire_grace_period()

        self.mock_stripe_cancel.side_effect = (
            stripe_module.error.InvalidRequestError(
                "No such subscription: 'sub_test_acme'",
                param="id",
                code="resource_missing",
            )
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 1)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.free_plan)

    def test_second_run_does_nothing(self):
        self.expire_grace_period()

        self.assertEqual(process_expired_grace_periods(), 1)
        self.assertEqual(process_expired_grace_periods(), 0)

        self.mock_stripe_cancel.assert_called_once()

    def test_members_are_notified_of_downgrade(self):
        from apps.notifications.models import Notification

        self.expire_grace_period()

        process_expired_grace_periods()

        self.assertTrue(
            Notification.objects.filter(
                organization=self.organization,
                user=self.owner,
                title="Downgraded to Free",
            ).exists()
        )

    def test_expired_past_due_subscription_is_downgraded_to_free(self):
        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.payment_failed_at = (
            timezone.now() - timedelta(days=8)
        )
        self.subscription.payment_retry_count = 3
        self.subscription.grace_period_end = (
            timezone.now() - timedelta(hours=1)
        )

        self.subscription.save(
            update_fields=[
                "status",
                "payment_failed_at",
                "payment_retry_count",
                "grace_period_end",
            ]
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 1)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.plan,
            self.free_plan,
        )

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )

        self.assertIsNone(
            self.subscription.payment_failed_at
        )

        self.assertEqual(
            self.subscription.payment_retry_count,
            0,
        )

        self.assertIsNone(
            self.subscription.grace_period_end
        )

    def test_non_expired_grace_period_is_not_processed(self):
        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.payment_failed_at = timezone.now()
        self.subscription.payment_retry_count = 1
        self.subscription.grace_period_end = (
            timezone.now() + timedelta(days=3)
        )

        self.subscription.save(
            update_fields=[
                "status",
                "payment_failed_at",
                "payment_retry_count",
                "grace_period_end",
            ]
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 0)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.PAST_DUE,
        )

        self.assertEqual(
            self.subscription.plan,
            self.pro_plan,
        )

    def test_active_subscription_is_not_processed(self):
        self.subscription.status = Subscription.Status.ACTIVE
        self.subscription.grace_period_end = (
            timezone.now() - timedelta(days=1)
        )

        self.subscription.save(
            update_fields=[
                "status",
                "grace_period_end",
            ]
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 0)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )

        self.assertEqual(
            self.subscription.plan,
            self.pro_plan,
        )

    def test_past_due_without_grace_period_is_not_processed(self):
        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.grace_period_end = None

        self.subscription.save(
            update_fields=[
                "status",
                "grace_period_end",
            ]
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 0)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.PAST_DUE,
        )

    def test_multiple_expired_subscriptions_are_processed(self):
        second_owner = User.objects.create_user(
            email="second-owner@example.com",
            password="TestPassword123",
        )

        second_org = Organization.objects.create(
            name="Second Org",
            slug="second-org",
            billing_email="billing@second.org",
        )

        Membership.objects.create(
            user=second_owner,
            organization=second_org,
            role=Membership.Role.OWNER,
        )

        second_subscription = Subscription.objects.create(
            organization=second_org,
            plan=self.enterprise_plan,
            status=Subscription.Status.PAST_DUE,
            grace_period_end=timezone.now() - timedelta(days=1),
            payment_failed_at=timezone.now() - timedelta(days=8),
            payment_retry_count=2,
        )

        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.grace_period_end = (
            timezone.now() - timedelta(days=1)
        )
        self.subscription.payment_failed_at = (
            timezone.now() - timedelta(days=8)
        )
        self.subscription.payment_retry_count = 2

        self.subscription.save(
            update_fields=[
                "status",
                "grace_period_end",
                "payment_failed_at",
                "payment_retry_count",
            ]
        )

        result = process_expired_grace_periods()

        self.assertEqual(result, 2)

        self.subscription.refresh_from_db()
        second_subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.plan,
            self.free_plan,
        )

        self.assertEqual(
            second_subscription.plan,
            self.free_plan,
        )

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )

        self.assertEqual(
            second_subscription.status,
            Subscription.Status.ACTIVE,
        )