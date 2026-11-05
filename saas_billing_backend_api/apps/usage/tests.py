from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.billing.models import Plan, Subscription
from apps.tenants.models import Membership, Organization

from .models import UsageRecord
from .views import get_current_usage


class UsageTestBase(APITestCase):

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
            is_active=True,
        )

        self.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            description="Enterprise plan",
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            api_request_limit=100000,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

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
        # Organization 1
        # ---------------------------------------------------------

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
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Organization 2
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # Subscription
        # ---------------------------------------------------------

        self.period_start = timezone.now() - timedelta(days=5)
        self.period_end = timezone.now() + timedelta(days=25)

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            current_period_start=self.period_start,
            current_period_end=self.period_end,
            stripe_customer_id="cus_test_usage",
            stripe_subscription_id="sub_test_usage",
        )

        self.other_subscription = Subscription.objects.create(
            organization=self.other_organization,
            plan=self.enterprise_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            current_period_start=self.period_start,
            current_period_end=self.period_end,
            stripe_customer_id="cus_other_usage",
            stripe_subscription_id="sub_other_usage",
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

    def record_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "usage-record",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def summary_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "usage-summary",
            kwargs={
                "organization_id": organization.id,
            },
        )


class UsageRecordModelTests(UsageTestBase):

    def test_usage_record_can_be_created(self):
        record = UsageRecord.objects.create(
            organization=self.organization,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=10,
        )

        self.assertEqual(
            record.organization,
            self.organization,
        )

        self.assertEqual(
            record.resource,
            UsageRecord.ResourceType.API_REQUEST,
        )

        self.assertEqual(
            record.quantity,
            10,
        )

    def test_usage_record_string_representation(self):
        record = UsageRecord.objects.create(
            organization=self.organization,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=25,
        )

        self.assertEqual(
            str(record),
            "Acme Corporation - API_REQUEST - 25",
        )


class CurrentUsageTests(UsageTestBase):

    def test_current_usage_returns_zero_when_no_records_exist(self):
        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            0,
        )

    def test_current_usage_sums_records_in_current_period(self):
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=10,
        )

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=20,
        )

        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            30,
        )

    def test_current_usage_ignores_records_before_period(self):
        old_record = UsageRecord.objects.create(
            organization=self.organization,
            quantity=100,
        )

        UsageRecord.objects.filter(
            id=old_record.id
        ).update(
            recorded_at=self.period_start - timedelta(days=1)
        )

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=25,
        )

        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            25,
        )

    def test_current_usage_ignores_records_after_period(self):
        future_record = UsageRecord.objects.create(
            organization=self.organization,
            quantity=100,
        )

        UsageRecord.objects.filter(
            id=future_record.id
        ).update(
            recorded_at=self.period_end + timedelta(seconds=1)
        )

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=15,
        )

        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            15,
        )

    def test_current_usage_only_counts_api_requests(self):
        UsageRecord.objects.create(
            organization=self.organization,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=30,
        )

        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            30,
        )

    def test_current_usage_is_tenant_scoped(self):
        UsageRecord.objects.create(
            organization=self.other_organization,
            quantity=500,
        )

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=25,
        )

        usage = get_current_usage(
            self.subscription
        )

        self.assertEqual(
            usage,
            25,
        )


class RecordUsageAPITests(UsageTestBase):

    def test_owner_can_record_usage(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["quantity"],
            10,
        )

        self.assertEqual(
            response.data["resource"],
            UsageRecord.ResourceType.API_REQUEST,
        )

        self.assertEqual(
            str(response.data["organization"]),
            str(self.organization.id),
        )

        self.assertEqual(
            UsageRecord.objects.filter(
                organization=self.organization
            ).count(),
            1,
        )

    def test_member_cannot_record_usage_manually(self):
        # Phase 7: manual recording is OWNER/ADMIN only; real usage
        # comes from the product API with an API key.
        self.authenticate(self.member)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 25,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertFalse(
            UsageRecord.objects.filter(
                organization=self.organization
            ).exists()
        )

    def test_usage_organization_is_taken_from_url(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "organization": str(
                    self.other_organization.id
                ),
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        record = UsageRecord.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            record.organization_id,
            self.organization.id,
        )

    def test_usage_resource_is_recorded_as_api_request(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "resource": UsageRecord.ResourceType.API_REQUEST,
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        record = UsageRecord.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            record.resource,
            UsageRecord.ResourceType.API_REQUEST,
        )

    def test_zero_quantity_is_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_negative_quantity_is_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": -5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_missing_quantity_is_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_usage_cannot_exceed_plan_limit(self):
        self.authenticate(self.owner)

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.pro_plan.api_request_limit - 10,
        )

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 11,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["detail"],
            "Usage limit exceeded.",
        )

        self.assertEqual(
            response.data["used"],
            self.pro_plan.api_request_limit - 10,
        )

        self.assertEqual(
            response.data["requested"],
            11,
        )

        self.assertEqual(
            response.data["limit"],
            self.pro_plan.api_request_limit,
        )

        self.assertEqual(
            response.data["remaining"],
            10,
        )

    def test_usage_can_reach_exact_plan_limit(self):
        self.authenticate(self.owner)

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.pro_plan.api_request_limit - 10,
        )

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            get_current_usage(
                self.subscription
            ),
            self.pro_plan.api_request_limit,
        )

    def test_usage_limit_is_based_on_subscription_plan(self):
        self.subscription.plan = self.free_plan
        self.subscription.save(
            update_fields=["plan"]
        )

        self.authenticate(self.owner)

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=995,
        )

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 6,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["limit"],
            1000,
        )

    def test_unauthenticated_user_cannot_record_usage(self):
        self.clear_auth()

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_cross_tenant_usage_record_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.record_url(self.organization),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_membership_cannot_record_usage(self):
        Membership.objects.filter(
            user=self.member,
            organization=self.organization,
        ).update(
            is_active=False
        )

        self.authenticate(self.member)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_organization_cannot_record_usage(self):
        self.organization.is_active = False
        self.organization.save(
            update_fields=["is_active"]
        )

        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(),
            {
                "quantity": 10,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class UsageSummaryAPITests(UsageTestBase):

    def test_owner_can_view_usage_summary(self):
        self.authenticate(self.owner)

        UsageRecord.objects.create(
            organization=self.organization,
            quantity=125,
        )

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["resource"],
            "API_REQUEST",
        )

        self.assertEqual(
            response.data["used"],
            125,
        )

        self.assertEqual(
            response.data["limit"],
            10000,
        )

        self.assertEqual(
            response.data["remaining"],
            9875,
        )

    def test_member_can_view_usage_summary(self):
        self.authenticate(self.member)

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_usage_summary_returns_zero_when_no_usage(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["used"],
            0,
        )

        self.assertEqual(
            response.data["limit"],
            10000,
        )

        self.assertEqual(
            response.data["remaining"],
            10000,
        )

    def test_usage_summary_is_tenant_scoped(self):
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=50,
        )

        UsageRecord.objects.create(
            organization=self.other_organization,
            quantity=500,
        )

        self.authenticate(self.other_owner)

        response = self.client.get(
            self.summary_url(
                self.other_organization
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["used"],
            500,
        )

        self.assertEqual(
            response.data["limit"],
            100000,
        )

    def test_cross_tenant_usage_summary_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.summary_url(
                self.organization
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_view_summary(self):
        self.clear_auth()

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_inactive_membership_cannot_view_summary(self):
        Membership.objects.filter(
            user=self.member,
            organization=self.organization,
        ).update(
            is_active=False
        )

        self.authenticate(self.member)

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_organization_cannot_view_summary(self):
        self.organization.is_active = False
        self.organization.save(
            update_fields=["is_active"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.summary_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

# =============================================================================
# Phase 7: usage period fixes
# =============================================================================


class UsagePeriodTests(UsageTestBase):

    def _record_at(self, when, quantity=1, organization=None):
        record = UsageRecord.objects.create(
            organization=organization or self.organization,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=quantity,
        )
        UsageRecord.objects.filter(pk=record.pk).update(recorded_at=when)
        return record

    def test_free_plan_without_period_resets_every_calendar_month(self):
        # FREE subscriptions never get a Stripe period. Old code then
        # counted usage over all time, so the limit never reset.
        self.subscription.plan = self.free_plan
        self.subscription.current_period_start = None
        self.subscription.current_period_end = None
        self.subscription.stripe_subscription_id = None
        self.subscription.save()

        now = timezone.now()
        last_month = now.replace(day=1) - timedelta(days=3)

        self._record_at(last_month, quantity=900)
        self._record_at(now, quantity=5)

        self.assertEqual(get_current_usage(self.subscription), 5)

    def test_stale_past_period_without_stripe_sub_still_counts_usage(self):
        # Downgraded to FREE by the grace-period task: Stripe sub id is
        # cleared, the old period stays. Old code counted only inside
        # that past period -> new usage was 0 -> no limit at all.
        self.subscription.plan = self.free_plan
        self.subscription.current_period_start = (
            timezone.now() - timedelta(days=70)
        )
        self.subscription.current_period_end = (
            timezone.now() - timedelta(days=40)
        )
        self.subscription.stripe_subscription_id = None
        self.subscription.save()

        self._record_at(timezone.now(), quantity=7)

        self.assertEqual(get_current_usage(self.subscription), 7)

    def test_paid_period_ended_but_renewal_pending_keeps_counting(self):
        # Renewal webhook not received yet: keep counting from the
        # period start instead of resetting to zero.
        start = timezone.now() - timedelta(days=31)
        self.subscription.current_period_start = start
        self.subscription.current_period_end = (
            timezone.now() - timedelta(hours=2)
        )
        self.subscription.save()

        self._record_at(start + timedelta(days=1), quantity=10)
        self._record_at(timezone.now(), quantity=3)

        self.assertEqual(get_current_usage(self.subscription), 13)

    def test_summary_includes_plan_and_period(self):
        self.authenticate(self.member)

        response = self.client.get(self.summary_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "PRO")
        self.assertEqual(response.data["period_start"], self.period_start)
        self.assertEqual(response.data["period_end"], self.period_end)

    def test_canceled_subscription_gets_free_plan_limit(self):
        from .services import get_usage_summary

        self.subscription.status = Subscription.Status.CANCELED
        self.subscription.save()

        summary = get_usage_summary(self.subscription)

        self.assertEqual(summary.limit, self.free_plan.api_request_limit)
        self.assertEqual(summary.plan_code, "FREE")


class ManualUsageAuditTests(UsageTestBase):

    def test_manual_record_is_audited(self):
        from apps.audit.models import AuditLog

        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(), {"quantity": 3}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = AuditLog.objects.get(action="USAGE_RECORDED_MANUALLY")
        self.assertEqual(log.user, self.owner)
        self.assertEqual(log.metadata["quantity"], 3)
        self.assertEqual(
            UsageRecord.objects.get(organization=self.organization).endpoint,
            "manual",
        )


# =============================================================================
# Phase 7: API key management (dashboard, JWT)
# =============================================================================


class ApiKeyTestMixin:

    def keys_url(self, organization=None):
        organization = organization or self.organization
        return reverse(
            "api-key-list",
            kwargs={"organization_id": organization.id},
        )

    def revoke_url(self, api_key, organization=None):
        organization = organization or self.organization
        return reverse(
            "api-key-revoke",
            kwargs={
                "organization_id": organization.id,
                "key_id": api_key.id,
            },
        )

    def make_key(self, organization=None, name="Server"):
        from .models import ApiKey

        return ApiKey.create_key(
            organization=organization or self.organization,
            name=name,
            created_by=self.owner,
        )


class ApiKeyManagementTests(ApiKeyTestMixin, UsageTestBase):

    def test_owner_can_create_key_and_plaintext_is_shown_once(self):
        from apps.audit.models import AuditLog

        from .models import ApiKey

        self.authenticate(self.owner)

        response = self.client.post(
            self.keys_url(), {"name": "Production"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        raw_key = response.data["key"]
        self.assertTrue(raw_key.startswith("sbk_"))

        api_key = ApiKey.objects.get(id=response.data["id"])
        self.assertEqual(api_key.organization, self.organization)
        self.assertEqual(api_key.created_by, self.owner)
        self.assertEqual(api_key.prefix, raw_key[:12])
        self.assertNotEqual(api_key.key_hash, raw_key)
        self.assertEqual(api_key.key_hash, ApiKey.hash_key(raw_key))
        self.assertTrue(
            AuditLog.objects.filter(
                action="API_KEY_CREATED",
                resource_id=str(api_key.id),
            ).exists()
        )

        list_response = self.client.get(self.keys_url())
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertNotIn("key", list_response.data[0])
        self.assertNotIn("key_hash", list_response.data[0])
        self.assertNotIn(raw_key, str(list_response.data))

    def test_blank_name_is_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.keys_url(), {"name": "   "}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_cannot_list_or_create_keys(self):
        self.make_key()
        self.authenticate(self.member)

        self.assertEqual(
            self.client.get(self.keys_url()).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                self.keys_url(), {"name": "x"}, format="json"
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cross_tenant_access_is_blocked(self):
        api_key, _ = self.make_key()
        self.authenticate(self.other_owner)

        # Other org's URL for our org's keys -> not a member -> 403.
        self.assertEqual(
            self.client.get(self.keys_url()).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Own org URL with our key's id -> key not in that org -> 404.
        response = self.client.delete(
            self.revoke_url(api_key, organization=self.other_organization)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        api_key.refresh_from_db()
        self.assertIsNone(api_key.revoked_at)

    def test_owner_can_revoke_key(self):
        from apps.audit.models import AuditLog

        api_key, _ = self.make_key()
        self.authenticate(self.owner)

        response = self.client.delete(self.revoke_url(api_key))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)
        self.assertEqual(api_key.revoked_by, self.owner)
        self.assertEqual(
            AuditLog.objects.filter(action="API_KEY_REVOKED").count(), 1
        )

        # Revoking twice is harmless and not audited again.
        self.client.delete(self.revoke_url(api_key))
        self.assertEqual(
            AuditLog.objects.filter(action="API_KEY_REVOKED").count(), 1
        )

    def test_active_key_limit(self):
        from .views import MAX_ACTIVE_API_KEYS

        keys = [
            self.make_key(name=f"k{i}")[0]
            for i in range(MAX_ACTIVE_API_KEYS)
        ]
        self.authenticate(self.owner)

        response = self.client.post(
            self.keys_url(), {"name": "one too many"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Revoked keys do not count.
        keys[0].revoke()
        response = self.client.post(
            self.keys_url(), {"name": "now ok"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_shows_requests_this_period_per_key(self):
        key_a, _ = self.make_key(name="A")
        key_b, _ = self.make_key(name="B")

        UsageRecord.objects.create(
            organization=self.organization, quantity=1, api_key=key_a
        )
        UsageRecord.objects.create(
            organization=self.organization, quantity=4, api_key=key_a
        )
        old = UsageRecord.objects.create(
            organization=self.organization, quantity=1, api_key=key_b
        )
        UsageRecord.objects.filter(pk=old.pk).update(
            recorded_at=self.period_start - timedelta(days=1)
        )

        self.authenticate(self.owner)
        response = self.client.get(self.keys_url())

        counts = {
            row["name"]: row["requests_this_period"]
            for row in response.data
        }
        self.assertEqual(counts, {"A": 5, "B": 0})


# =============================================================================
# Phase 7: product API (/api/v1/, API key)
# =============================================================================


class ProductAPITests(ApiKeyTestMixin, UsageTestBase):

    def setUp(self):
        super().setUp()
        self.api_key, self.raw_key = self.make_key()
        self.analyze_url = reverse("product-text-analyze")
        self.product_usage_url = reverse("product-usage")

    def call(self, text="Billing is fun. Billing pays the bills!",
             key=None, header="authorization"):
        key = self.raw_key if key is None else key
        extra = (
            {"HTTP_AUTHORIZATION": f"Api-Key {key}"}
            if header == "authorization"
            else {"HTTP_X_API_KEY": key}
        )
        return self.client.post(
            self.analyze_url, {"text": text}, format="json", **extra
        )

    def test_valid_key_returns_analysis_and_records_usage(self):
        response = self.call()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["words"], 7)
        self.assertEqual(response.data["sentences"], 2)
        self.assertEqual(
            response.data["top_keywords"][0],
            {"word": "billing", "count": 2},
        )

        record = UsageRecord.objects.get(organization=self.organization)
        self.assertEqual(record.quantity, 1)
        self.assertEqual(record.api_key, self.api_key)
        self.assertEqual(record.endpoint, "text.analyze")

        self.assertEqual(response["X-RateLimit-Limit"], "10000")
        self.assertEqual(response["X-RateLimit-Remaining"], "9999")
        self.assertEqual(
            response["X-RateLimit-Reset"],
            str(int(self.period_end.timestamp())),
        )

        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used_at)

    def test_x_api_key_header_also_works(self):
        response = self.call(header="x-api-key")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_or_wrong_key_is_401_and_not_metered(self):
        self.assertEqual(
            self.client.post(
                self.analyze_url, {"text": "hi"}, format="json"
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.call(key="sbk_wrong").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertFalse(UsageRecord.objects.exists())

    def test_revoked_key_is_rejected(self):
        self.api_key.revoke()

        response = self.call()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(UsageRecord.objects.exists())

    def test_jwt_is_not_accepted_on_product_api(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.analyze_url, {"text": "hello"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_key_is_not_accepted_on_dashboard_api(self):
        response = self.client.get(
            self.summary_url(),
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_input_is_not_metered(self):
        response = self.call(text="   ")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(UsageRecord.objects.exists())

    def test_over_limit_returns_429_and_records_nothing(self):
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.pro_plan.api_request_limit,
        )

        response = self.call()

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertEqual(response.data["remaining"], 0)
        self.assertEqual(response["X-RateLimit-Remaining"], "0")
        self.assertEqual(
            UsageRecord.objects.filter(api_key=self.api_key).count(), 0
        )

    def test_last_request_within_limit_is_allowed(self):
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.pro_plan.api_request_limit - 1,
        )

        self.assertEqual(self.call().status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.call().status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )

    def test_inactive_organization_key_is_rejected(self):
        self.organization.is_active = False
        self.organization.save()

        self.assertEqual(
            self.call().status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_usage_is_tenant_scoped(self):
        other_key, other_raw = self.make_key(
            organization=self.other_organization
        )

        self.call(key=other_raw)

        self.assertEqual(
            UsageRecord.objects.filter(
                organization=self.other_organization
            ).count(),
            1,
        )
        self.assertFalse(
            UsageRecord.objects.filter(
                organization=self.organization
            ).exists()
        )

    def test_product_usage_endpoint_is_not_metered(self):
        self.call()

        response = self.client.get(
            self.product_usage_url,
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["used"], 1)
        self.assertEqual(response.data["remaining"], 9999)
        self.assertEqual(UsageRecord.objects.count(), 1)

    def test_canceled_subscription_is_limited_to_free_quota(self):
        self.subscription.status = Subscription.Status.CANCELED
        self.subscription.save()
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.free_plan.api_request_limit,
        )

        response = self.call()

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertEqual(
            response.data["limit"], self.free_plan.api_request_limit
        )


class TextInsightsTests(APITestCase):

    def test_analysis(self):
        from .text_insights import analyze_text

        result = analyze_text(
            "The invoice was paid.\n\nThe invoice was late! Why?"
        )

        self.assertEqual(result["words"], 9)
        self.assertEqual(result["sentences"], 3)
        self.assertEqual(result["paragraphs"], 2)
        self.assertEqual(result["reading_time_seconds"], 3)
        self.assertEqual(
            result["top_keywords"][0], {"word": "invoice", "count": 2}
        )
        self.assertNotIn(
            "the", [k["word"] for k in result["top_keywords"]]
        )
