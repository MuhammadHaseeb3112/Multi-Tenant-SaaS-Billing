from datetime import date, timedelta
from django.utils import timezone
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.billing.models import Plan, Subscription
from apps.invoices.models import Invoice, Payment


def record_payment(invoice, paid_on=None):
    """
    Phase 5+: revenue comes from Payment rows (money received), so a
    paid invoice in these tests also gets the Payment the app would
    have recorded.
    """
    from datetime import datetime, time, timezone as dt_timezone

    paid_on = paid_on or invoice.issue_date

    return Payment.objects.create(
        organization=invoice.organization,
        invoice=invoice,
        amount=invoice.total,
        currency=invoice.currency,
        method=Payment.Method.MANUAL,
        paid_at=datetime.combine(paid_on, time(12), tzinfo=dt_timezone.utc),
    )
from apps.tenants.models import Membership, Organization




class AnalyticsTestBase(APITestCase):

    def setUp(self):
        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

        now = timezone.now()


        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="TestPassword123",
            first_name="Owner",
            last_name="User",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123",
            first_name="Member",
            last_name="User",
        )

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123",
            first_name="Other",
            last_name="Owner",
        )

        # ---------------------------------------------------------
        # Organizations
        # ---------------------------------------------------------

        self.organization = Organization.objects.create(
            name="Acme Corporation",
            slug="acme-corporation",
            billing_email="billing@acme.com",
            is_active=True,
        )

        self.other_organization = Organization.objects.create(
            name="Other Corporation",
            slug="other-corporation",
            billing_email="billing@other.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

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
            monthly_price=Decimal("100.00"),
            annual_price=Decimal("1080.00"),
            api_request_limit=10000,
            is_active=True,
        )

        self.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            description="Enterprise plan",
            monthly_price=Decimal("300.00"),
            annual_price=Decimal("3000.00"),
            api_request_limit=50000,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Current subscription
        # ---------------------------------------------------------

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,

            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

        # ---------------------------------------------------------
        # Other organization subscription
        # ---------------------------------------------------------

    

        self.other_subscription = Subscription.objects.create(
            organization=self.other_organization,
            plan=self.enterprise_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,

            

            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

    # -------------------------------------------------------------
    # Authentication
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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

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

    def url(self, name, organization=None):
        organization = (
            organization or self.organization
        )

        return reverse(
            name,
            kwargs={
                "organization_id": organization.id,
            },
        )


class MRRTests(AnalyticsTestBase):

    def test_monthly_subscription_mrr(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-mrr")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "100.00",
        )

        self.assertEqual(
            response.data["plan"],
            "PRO",
        )

        self.assertEqual(
            response.data["interval"],
            Subscription.Interval.MONTHLY,
        )

        self.assertEqual(
            response.data["subscription_status"],
            Subscription.Status.ACTIVE,
        )

    def test_annual_subscription_mrr_is_divided_by_twelve(self):
        self.subscription.interval = (
            Subscription.Interval.ANNUAL
        )
        self.subscription.save(
            update_fields=["interval"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-mrr")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "90.00",
        )

    def test_free_plan_has_zero_mrr(self):
        self.subscription.plan = self.free_plan
        self.subscription.save(
            update_fields=["plan"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-mrr")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "0.00",
        )

    def test_inactive_subscription_has_zero_mrr(self):
        self.subscription.status = (
            Subscription.Status.CANCELED
        )
        self.subscription.save(
            update_fields=["status"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-mrr")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "0.00",
        )

    def test_cross_tenant_mrr_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.url(
                "analytics-mrr",
                self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_mrr_is_rejected(self):
        self.clear_auth()

        response = self.client.get(
            self.url("analytics-mrr")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class SubscriptionAnalyticsTests(AnalyticsTestBase):

    def test_subscription_breakdown(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-subscriptions")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["subscriptions"],
            {
                "active": 1,
                "trialing": 0,
                "past_due": 0,
                "canceled": 0,
            },
        )

        self.assertEqual(
            response.data["current_subscription"]["plan"],
            "PRO",
        )

    def test_subscription_status_counts(self):
        # Subscription is OneToOne with Organization.
        # Therefore, one organization can only have one
        # current subscription.
        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-subscriptions")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["subscriptions"],
            {
                "active": 1,
                "trialing": 0,
                "past_due": 0,
                "canceled": 0,
            },
        )

    def test_cross_tenant_subscription_analytics_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.url(
                "analytics-subscriptions",
                self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class RevenueTrendTests(AnalyticsTestBase):

    def create_paid_invoice(
        self,
        invoice_number,
        issue_date,
        total,
    ):
        invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number=invoice_number,
            status=Invoice.Status.PAID,
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=30),
            currency=Invoice.Currency.USD,
            subtotal=Decimal(total),
            tax=Decimal("0.00"),
            total=Decimal(total),
            billing_email="billing@acme.com",
        )

        record_payment(invoice)

        return invoice

    def test_revenue_trend_groups_paid_invoices_by_month(self):
        self.create_paid_invoice(
            "INV-000002",
            date(2026, 1, 10),
            "100.00",
        )

        self.create_paid_invoice(
            "INV-000003",
            date(2026, 1, 20),
            "50.00",
        )

        self.create_paid_invoice(
            "INV-000004",
            date(2026, 2, 5),
            "200.00",
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-revenue")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["trend"],
            [
                {
                    "month": "2026-01",
                    "revenue": "150.00",
                },
                {
                    "month": "2026-02",
                    "revenue": "200.00",
                },
            ],
        )

    def test_unpaid_invoices_are_excluded(self):
        Invoice.objects.create(
            organization=self.organization,
            invoice_number="INV-000002",
            status=Invoice.Status.OPEN,
            issue_date=date(2026, 1, 10),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("500.00"),
            tax=Decimal("0.00"),
            total=Decimal("500.00"),
            billing_email="billing@acme.com",
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-revenue")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["trend"],
            [],
        )

    def test_cross_tenant_revenue_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.url(
                "analytics-revenue",
                self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_revenue_is_rejected(self):
        self.clear_auth()

        response = self.client.get(
            self.url("analytics-revenue")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class ChurnTests(AnalyticsTestBase):

    def test_zero_churn_when_no_canceled_subscriptions(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-churn")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["churned"],
            0,
        )

        self.assertEqual(
            response.data["churn_rate"],
            0,
        )

    def test_churn_rate_is_calculated_from_snapshot(self):
        # Subscription is OneToOne with Organization, so we
        # cannot create multiple subscription rows for the
        # same organization. Instead, change the current
        # subscription to CANCELED and verify the snapshot.
        self.subscription.status = (
            Subscription.Status.CANCELED
        )
        self.subscription.save(
            update_fields=["status"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-churn")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["subscriptions"]["total"],
            1,
        )

        self.assertEqual(
            response.data["churned"],
            1,
        )

        self.assertEqual(
            response.data["churn_rate"],
            100.0,
        )

    def test_cross_tenant_churn_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.url(
                "analytics-churn",
                self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class AnalyticsOverviewTests(AnalyticsTestBase):

    def test_overview_returns_combined_analytics(self):
        paid_invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number="INV-000002",
            status=Invoice.Status.PAID,
            issue_date=date(2026, 1, 10),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("250.00"),
            tax=Decimal("0.00"),
            total=Decimal("250.00"),
            billing_email="billing@acme.com",
        )

        record_payment(paid_invoice)

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-overview")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "100.00",
        )

        self.assertEqual(
            response.data["current_subscription"]["plan"],
            "PRO",
        )

        self.assertEqual(
            response.data["active_subscriptions"],
            1,
        )

        self.assertEqual(
            response.data["subscription_breakdown"]["total"],
            1,
        )

        self.assertEqual(
            response.data["churn"]["churned"],
            0,
        )

        self.assertEqual(
            response.data["revenue_trend"],
            [
                {
                    "month": "2026-01",
                    "revenue": "250.00",
                }
            ],
        )

    def test_overview_handles_no_subscriptions(self):
        self.subscription.delete()

        self.authenticate(self.owner)

        response = self.client.get(
            self.url("analytics-overview")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["mrr"],
            "0.00",
        )

        self.assertIsNone(
            response.data["current_subscription"]["plan"]
        )

        self.assertEqual(
            response.data["active_subscriptions"],
            0,
        )

        self.assertEqual(
            response.data["churn"]["churned"],
            0,
        )

        self.assertEqual(
            response.data["churn"]["churn_rate"],
            0,
        )

    def test_cross_tenant_overview_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.url(
                "analytics-overview",
                self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_overview_is_rejected(self):
        self.clear_auth()

        response = self.client.get(
            self.url("analytics-overview")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

# =============================================================================
# PHASE 6 — revenue from payments, platform analytics
# =============================================================================


class PaymentBasedRevenueTests(AnalyticsTestBase):

    def make_payment(self, organization, amount, paid_at,
                     method=Payment.Method.STRIPE,
                     payment_status=Payment.Status.SUCCEEDED,
                     currency="USD"):
        return Payment.objects.create(
            organization=organization,
            amount=Decimal(amount),
            currency=currency,
            method=method,
            status=payment_status,
            paid_at=paid_at,
        )

    def test_stripe_payment_without_local_invoice_counts(self):
        from datetime import datetime, timezone as dt_timezone

        # A Stripe subscription payment: before Phase 5 this never
        # reached analytics, so "paid revenue" stayed 0.
        self.make_payment(
            self.organization,
            "100.00",
            datetime(2026, 3, 5, tzinfo=dt_timezone.utc),
        )

        self.authenticate(self.owner)

        response = self.client.get(self.url("analytics-revenue"))

        self.assertEqual(
            response.data["trend"],
            [{"month": "2026-03", "revenue": "100.00"}],
        )

    def test_refunded_payments_are_excluded(self):
        self.make_payment(
            self.organization,
            "40.00",
            timezone.now(),
            payment_status=Payment.Status.REFUNDED,
        )

        self.authenticate(self.owner)

        response = self.client.get(self.url("analytics-overview"))

        self.assertEqual(response.data["revenue_trend"], [])
        self.assertEqual(response.data["total_paid"], "0.00")

    def test_overview_total_paid_is_tenant_scoped(self):
        self.make_payment(self.organization, "25.00", timezone.now())
        self.make_payment(self.other_organization, "999.00", timezone.now())

        self.authenticate(self.owner)

        response = self.client.get(self.url("analytics-overview"))

        self.assertEqual(response.data["total_paid"], "25.00")

    def test_annual_mrr_is_rounded_to_cents(self):
        self.subscription.interval = Subscription.Interval.ANNUAL
        self.subscription.plan = self.enterprise_plan  # 3000 / 12 = 250
        self.subscription.save()

        self.authenticate(self.owner)

        response = self.client.get(self.url("analytics-mrr"))

        self.assertEqual(response.data["mrr"], "250.00")


class PlatformOverviewTests(AnalyticsTestBase):

    def setUp(self):
        super().setUp()

        self.staff = User.objects.create_user(
            email="staff@platform.example",
            password="TestPassword123",
            is_staff=True,
        )

    def platform_url(self):
        return reverse("analytics-platform-overview")

    def test_owner_of_an_organization_is_forbidden(self):
        self.authenticate(self.owner)

        response = self.client.get(self.platform_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_is_rejected(self):
        response = self.client.get(self.platform_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_staff_sees_platform_metrics(self):
        from datetime import timedelta as td

        # Third org: churned (downgraded to FREE 5 days ago).
        churned_org = Organization.objects.create(
            name="Churned Org",
            slug="churned-org",
            billing_email="c@churned.example",
        )
        Subscription.objects.create(
            organization=churned_org,
            plan=self.free_plan,
            status=Subscription.Status.ACTIVE,
            canceled_at=timezone.now() - td(days=5),
        )

        Payment.objects.create(
            organization=self.organization,
            amount=Decimal("100.00"),
            method=Payment.Method.STRIPE,
            paid_at=timezone.now(),
        )
        Payment.objects.create(
            organization=self.other_organization,
            amount=Decimal("50.00"),
            method=Payment.Method.MANUAL,
            paid_at=timezone.now(),
        )
        Payment.objects.create(
            organization=self.other_organization,
            amount=Decimal("5000.00"),
            currency="PKR",
            method=Payment.Method.MANUAL,
            paid_at=timezone.now(),
        )

        self.authenticate(self.staff)

        response = self.client.get(self.platform_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["organizations"], 3)
        # PRO monthly 100 + ENTERPRISE monthly 300
        self.assertEqual(data["mrr"], "400.00")
        self.assertEqual(data["arr"], "4800.00")
        self.assertEqual(data["paying_subscriptions"], 2)
        self.assertEqual(data["arpa"], "200.00")
        self.assertEqual(data["plans"]["PRO"]["mrr"], "100.00")
        self.assertEqual(data["plans"]["FREE"]["paying"], 0)
        self.assertEqual(data["churn"]["churned"], 1)
        # 1 churned / (2 paying + 1 churned)
        self.assertEqual(data["churn"]["churn_rate"], 33.33)
        self.assertEqual(data["revenue"]["total"], "150.00")
        self.assertEqual(
            data["revenue"]["by_method"],
            {"STRIPE": "100.00", "MANUAL": "50.00"},
        )
        self.assertEqual(data["revenue"]["other_currency_payments"], 1)

    def test_past_due_is_not_counted_in_mrr(self):
        self.other_subscription.status = Subscription.Status.PAST_DUE
        self.other_subscription.save()

        self.authenticate(self.staff)

        response = self.client.get(self.platform_url())

        self.assertEqual(response.data["mrr"], "100.00")
        self.assertEqual(
            response.data["subscription_status"]["past_due"],
            1,
        )
