"""
Per-organization usage deals (UsageLimitOverride).

Two orgs on the same plan can get different limits / overage terms,
and a change can be scheduled ahead with start/end dates.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.billing.models import Subscription

from .models import UsageLimitOverride, UsageRecord, active_override_for
from .overage import calculate_period_overage
from .services import (
    UsageLimitExceeded,
    get_usage_summary,
    get_usage_terms,
    record_usage,
)
from .tests import UsageTestBase


class UsageLimitOverrideTests(UsageTestBase):

    def setUp(self):
        super().setUp()
        self.pro_plan.overage_price_per_1000 = Decimal("2.00")
        self.pro_plan.max_overage_requests = 500
        self.pro_plan.save()

    def deal(self, **kwargs):
        kwargs.setdefault("organization", self.organization)
        override = UsageLimitOverride(**kwargs)
        override.full_clean()
        override.save()
        return override

    # -------------------------------------------------------------
    # Which numbers apply
    # -------------------------------------------------------------

    def test_without_deal_plan_terms_apply(self):
        terms = get_usage_terms(self.subscription)

        self.assertEqual(terms.source, "plan")
        self.assertEqual(terms.limit, 10000)
        self.assertEqual(terms.overage_price_per_1000, Decimal("2.00"))
        self.assertEqual(terms.max_overage_requests, 500)

    def test_deal_replaces_only_the_fields_that_are_set(self):
        self.deal(api_request_limit=150)

        terms = get_usage_terms(self.subscription)

        self.assertEqual(terms.source, "custom")
        self.assertEqual(terms.limit, 150)
        # Not set in the deal -> plan values.
        self.assertEqual(terms.overage_price_per_1000, Decimal("2.00"))
        self.assertEqual(terms.max_overage_requests, 500)
        self.assertEqual(terms.plan_limit, 10000)

    def test_two_orgs_on_same_plan_get_different_limits(self):
        self.other_subscription.plan = self.pro_plan
        self.other_subscription.save()
        self.deal(api_request_limit=150)

        self.assertEqual(get_usage_terms(self.subscription).limit, 150)
        self.assertEqual(get_usage_terms(self.other_subscription).limit, 10000)

    def test_price_zero_turns_overage_off_for_this_org(self):
        self.deal(overage_price_per_1000=Decimal("0.00"))

        summary = get_usage_summary(self.subscription)

        self.assertFalse(summary.overage_enabled)

    def test_custom_price_and_cap(self):
        self.deal(
            overage_price_per_1000=Decimal("1.50"),
            max_overage_requests=10,
        )

        summary = get_usage_summary(self.subscription)

        self.assertTrue(summary.overage_enabled)
        self.assertEqual(summary.overage_price_per_1000, Decimal("1.50"))
        self.assertEqual(summary.max_overage_requests, 10)

    def test_no_overage_cap(self):
        self.deal(no_overage_cap=True)

        self.assertIsNone(get_usage_summary(self.subscription).max_overage_requests)

    def test_canceled_org_does_not_keep_its_deal(self):
        self.deal(api_request_limit=50000)
        self.subscription.status = Subscription.Status.CANCELED
        self.subscription.save()

        terms = get_usage_terms(self.subscription)

        self.assertEqual(terms.source, "plan")
        self.assertEqual(terms.limit, 1000)  # FREE plan

    # -------------------------------------------------------------
    # Scheduling ("100 this month, 80 next month")
    # -------------------------------------------------------------

    def test_scheduled_change(self):
        now = timezone.now()
        next_month = now + timedelta(days=30)

        self.deal(api_request_limit=100, ends_at=next_month)
        self.deal(api_request_limit=80, starts_at=next_month)

        self.assertEqual(get_usage_terms(self.subscription, now).limit, 100)
        self.assertEqual(
            get_usage_terms(self.subscription, next_month + timedelta(hours=1)).limit,
            80,
        )

    def test_future_deal_is_not_active_yet(self):
        self.deal(
            api_request_limit=5,
            starts_at=timezone.now() + timedelta(days=3),
        )

        self.assertIsNone(active_override_for(self.organization.id))
        self.assertEqual(get_usage_terms(self.subscription).limit, 10000)

    def test_expired_deal_stops_applying(self):
        self.deal(
            api_request_limit=5,
            starts_at=timezone.now() - timedelta(days=10),
            ends_at=timezone.now() - timedelta(days=1),
        )

        self.assertEqual(get_usage_terms(self.subscription).limit, 10000)

    # -------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------

    def test_overlapping_deals_are_rejected(self):
        self.deal(api_request_limit=100)

        with self.assertRaises(ValidationError):
            self.deal(
                api_request_limit=80,
                starts_at=timezone.now() + timedelta(days=30),
            )

    def test_end_must_be_after_start(self):
        start = timezone.now()

        with self.assertRaises(ValidationError):
            self.deal(starts_at=start, ends_at=start - timedelta(days=1))

    def test_cap_and_no_cap_together_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.deal(no_overage_cap=True, max_overage_requests=5)

    def test_deals_of_other_orgs_do_not_overlap_each_other(self):
        self.deal(api_request_limit=100)
        # Same window, different organization: allowed.
        self.deal(organization=self.other_organization, api_request_limit=100)

    # -------------------------------------------------------------
    # Enforcement and billing
    # -------------------------------------------------------------

    def test_custom_limit_is_enforced(self):
        self.deal(api_request_limit=2, overage_price_per_1000=Decimal("0"))

        record_usage(organization_id=self.organization.id, quantity=2)

        with self.assertRaises(UsageLimitExceeded):
            record_usage(organization_id=self.organization.id, quantity=1)

    def test_custom_cap_is_enforced(self):
        self.deal(api_request_limit=2, max_overage_requests=1)

        record_usage(organization_id=self.organization.id, quantity=3)

        with self.assertRaises(UsageLimitExceeded):
            record_usage(organization_id=self.organization.id, quantity=1)

    def test_period_billing_uses_the_deal(self):
        start = self.period_start
        end = self.period_end
        self.deal(
            api_request_limit=1000,
            overage_price_per_1000=Decimal("5.00"),
            starts_at=start - timedelta(days=1),
        )
        UsageRecord.objects.create(
            organization=self.organization,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=3000,
            recorded_at=start + timedelta(hours=1),
        )

        used, included, overage, price, amount = calculate_period_overage(
            self.subscription, start, end
        )

        self.assertEqual(included, 1000)
        self.assertEqual(overage, 2000)
        self.assertEqual(price, Decimal("5.00"))
        self.assertEqual(amount, Decimal("10.00"))

    def test_summary_api_shows_custom_source(self):
        self.deal(api_request_limit=150)
        self.client.force_authenticate(self.owner)

        summary = get_usage_summary(self.subscription).as_dict()

        self.assertEqual(summary["limit"], 150)
        self.assertEqual(summary["limit_source"], "custom")
        self.assertEqual(summary["plan_limit"], 10000)
