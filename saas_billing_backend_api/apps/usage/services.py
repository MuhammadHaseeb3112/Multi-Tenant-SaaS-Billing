"""
Usage metering: billing-period calculation, limit checks and recording.

Every place that records API usage (the product API and the manual
dashboard endpoint) goes through ``record_usage`` so the limit is
enforced the same way, under a row lock.
"""

from dataclasses import dataclass
from decimal import ROUND_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.billing.models import Plan, Subscription

from .models import UsageRecord, active_override_for


# Subscriptions in these states do not get their paid plan's limit.
# They fall back to the FREE plan's limit (a canceled org keeps working
# like a free org instead of keeping PRO quota or being locked out).
INACTIVE_STATUSES = {
    Subscription.Status.CANCELED,
    Subscription.Status.UNPAID,
}


# Only subscriptions in good standing may run into paid overage.
# PAST_DUE orgs are already behind on payment: hard limit, no new debt.
OVERAGE_STATUSES = {
    Subscription.Status.ACTIVE,
    Subscription.Status.TRIALING,
}


def calculate_overage_amount(overage_requests, price_per_1000):
    """
    Money for ``overage_requests`` at ``price_per_1000``, rounded UP to
    the cent (never undercharge by rounding).
    """

    if overage_requests <= 0 or not price_per_1000:
        return Decimal("0.00")

    return (
        Decimal(overage_requests) * Decimal(price_per_1000) / 1000
    ).quantize(Decimal("0.01"), rounding=ROUND_UP)


def overage_allowed(subscription, price_per_1000):
    return bool(
        price_per_1000
        and price_per_1000 > 0
        and subscription.status in OVERAGE_STATUSES
        and subscription.stripe_subscription_id
        and subscription.stripe_customer_id
    )


class UsageLimitExceeded(Exception):
    def __init__(self, summary, requested):
        self.summary = summary
        self.requested = requested
        super().__init__("Usage limit exceeded.")


class NoSubscription(Exception):
    pass


@dataclass
class UsageSummary:
    used: int
    limit: int
    period_start: object
    period_end: object
    plan_code: str
    overage_enabled: bool = False
    overage_price_per_1000: Decimal = Decimal("0.00")
    max_overage_requests: object = None
    # "plan" = the plan's numbers, "custom" = an organization deal.
    limit_source: str = "plan"
    plan_limit: object = None

    @property
    def remaining(self):
        return max(self.limit - self.used, 0)

    @property
    def overage_requests(self):
        return max(self.used - self.limit, 0)

    @property
    def estimated_overage_amount(self):
        return calculate_overage_amount(
            self.overage_requests, self.overage_price_per_1000
        )

    def allows(self, quantity):
        """
        Can ``quantity`` more requests be recorded?
        """

        new_used = self.used + quantity

        if new_used <= self.limit:
            return True

        if not self.overage_enabled:
            return False

        if self.max_overage_requests is None:
            return True

        return new_used - self.limit <= self.max_overage_requests

    def as_dict(self):
        return {
            "resource": UsageRecord.ResourceType.API_REQUEST,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining,
            "plan": self.plan_code,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "overage_enabled": self.overage_enabled,
            "overage_requests": self.overage_requests,
            "overage_price_per_1000": str(self.overage_price_per_1000),
            "max_overage_requests": self.max_overage_requests,
            "estimated_overage_amount": str(
                self.estimated_overage_amount
            ),
            "limit_source": self.limit_source,
            "plan_limit": self.plan_limit,
        }


def _calendar_month(now):
    start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    return start, end


def get_usage_period(subscription, now=None):
    """
    Return ``(start, end)`` of the window usage is counted in.
    ``end`` may be None (open window).

    - Stripe period known and ``now`` inside it -> that period.
    - Paid Stripe subscription whose period end has passed (renewal
      webhook not received yet) -> from period start, open-ended, so
      usage keeps being counted instead of silently resetting.
    - Otherwise (FREE plans never get a Stripe period; downgraded or
      canceled subscriptions keep a stale one) -> current calendar
      month in UTC.

    Previously FREE orgs had no period at all, so their usage was
    counted over all time and never reset, and a downgraded org with a
    stale past period had no usage counted at all (no limit).
    """

    now = now or timezone.now()
    start = subscription.current_period_start
    end = subscription.current_period_end

    if start and end and start <= now < end:
        return start, end

    if (
        start
        and subscription.stripe_subscription_id
        and subscription.status not in INACTIVE_STATUSES
        and start <= now
    ):
        return start, None

    return _calendar_month(now)


def get_effective_plan(subscription):
    if subscription.status in INACTIVE_STATUSES:
        free_plan = Plan.objects.filter(code="FREE").first()
        if free_plan:
            return free_plan

    return subscription.plan


@dataclass
class UsageTerms:
    """The numbers that apply to one organization at one moment."""

    limit: int
    overage_price_per_1000: Decimal
    max_overage_requests: object
    source: str
    plan_code: str
    plan_limit: int


def get_usage_terms(subscription, at=None):
    """
    Plan terms, replaced field-by-field by the organization's active
    ``UsageLimitOverride`` (if any). Canceled/unpaid orgs fall back to
    the FREE plan and do not keep custom deals.
    """

    plan = get_effective_plan(subscription)

    terms = UsageTerms(
        limit=plan.api_request_limit,
        overage_price_per_1000=plan.overage_price_per_1000 or Decimal("0.00"),
        max_overage_requests=plan.max_overage_requests,
        source="plan",
        plan_code=plan.code,
        plan_limit=plan.api_request_limit,
    )

    if subscription.status in INACTIVE_STATUSES:
        return terms

    override = active_override_for(subscription.organization_id, at)

    if override is None:
        return terms

    terms.source = "custom"

    if override.api_request_limit is not None:
        terms.limit = override.api_request_limit

    if override.overage_price_per_1000 is not None:
        terms.overage_price_per_1000 = override.overage_price_per_1000

    if override.no_overage_cap:
        terms.max_overage_requests = None
    elif override.max_overage_requests is not None:
        terms.max_overage_requests = override.max_overage_requests

    return terms


def get_current_usage(subscription, now=None):
    """
    API usage of the subscription's organization in the current period.
    """

    start, end = get_usage_period(subscription, now)

    filters = {
        "organization_id": subscription.organization_id,
        "resource": UsageRecord.ResourceType.API_REQUEST,
        "recorded_at__gte": start,
    }

    if end:
        filters["recorded_at__lt"] = end

    return (
        UsageRecord.objects
        .filter(**filters)
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )


def get_usage_summary(subscription, now=None):
    start, end = get_usage_period(subscription, now)
    terms = get_usage_terms(subscription, now)

    enabled = overage_allowed(subscription, terms.overage_price_per_1000)

    return UsageSummary(
        used=get_current_usage(subscription, now),
        limit=terms.limit,
        period_start=start,
        period_end=end,
        plan_code=terms.plan_code,
        overage_enabled=enabled,
        overage_price_per_1000=(
            terms.overage_price_per_1000 if enabled else Decimal("0.00")
        ),
        max_overage_requests=(
            terms.max_overage_requests if enabled else None
        ),
        limit_source=terms.source,
        plan_limit=terms.plan_limit,
    )


def record_usage(
    *,
    organization_id,
    quantity=1,
    api_key=None,
    endpoint="",
):
    """
    Check the plan limit (and overage allowance) and record usage
    atomically.

    The organization's subscription row is locked, so concurrent
    requests cannot together go over the limit.

    Returns ``(usage_record, summary_after)``.
    Raises ``NoSubscription`` or ``UsageLimitExceeded``.
    """

    with transaction.atomic():
        subscription = (
            Subscription.objects
            .select_for_update(of=("self",))
            .select_related("plan")
            .filter(organization_id=organization_id)
            .first()
        )

        if subscription is None:
            raise NoSubscription()

        summary = get_usage_summary(subscription)

        if not summary.allows(quantity):
            raise UsageLimitExceeded(summary, quantity)

        usage_record = UsageRecord.objects.create(
            organization_id=organization_id,
            resource=UsageRecord.ResourceType.API_REQUEST,
            quantity=quantity,
            api_key=api_key,
            endpoint=endpoint,
        )

        summary.used += quantity

    return usage_record, summary
