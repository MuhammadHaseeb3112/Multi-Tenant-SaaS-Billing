from decimal import Decimal

from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import Subscription
from apps.invoices.models import Invoice, Payment

# Money kept after refunds. Revenue figures always use this, over
# Payment.COLLECTED_STATUSES (SUCCEEDED + PARTIALLY_REFUNDED).
NET_AMOUNT = ExpressionWrapper(
    F("amount") - F("amount_refunded"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)
from apps.tenants.models import Organization


def monthly_value(subscription):
    """
    Monthly recurring value of one subscription (annual price / 12).
    Zero for FREE plans and for subscriptions that are not
    currently billing (only ACTIVE and TRIALING count).
    """

    if subscription.plan.code == "FREE":
        return Decimal("0.00")

    if subscription.status not in (
        Subscription.Status.ACTIVE,
        Subscription.Status.TRIALING,
    ):
        return Decimal("0.00")

    if subscription.interval == Subscription.Interval.ANNUAL:
        return (
            subscription.plan.annual_price / Decimal("12")
        ).quantize(Decimal("0.01"))

    return subscription.plan.monthly_price


def payment_trend(payments):
    """
    Monthly totals of money actually received (Payment rows), by the
    date the money arrived. Replaces the old trend built from PAID
    invoices, which missed Stripe subscription payments entirely.
    """

    rows = (
        payments
        .filter(status__in=Payment.COLLECTED_STATUSES)
        .annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(revenue=Sum(NET_AMOUNT))
        .order_by("month")
    )

    return [
        {
            "month": row["month"].strftime("%Y-%m"),
            "revenue": f"{row['revenue']:.2f}",
        }
        for row in rows
    ]

from apps.tenants.permissions import IsOrganizationMember


class MRRView(APIView):
    """
    Return the current Monthly Recurring Revenue
    for an organization.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):

        subscription = get_object_or_404(
            Subscription.objects.select_related("plan"),
            organization_id=organization_id,
        )

        mrr = monthly_value(subscription)

        return Response(
            {
                "organization_id": str(
                    subscription.organization_id
                ),
                "currency": "USD",
                "mrr": f"{mrr:.2f}",
                "plan": subscription.plan.code,
                "interval": subscription.interval,
                "subscription_status": subscription.status,
            },
            status=status.HTTP_200_OK,
        )


class SubscriptionAnalyticsView(APIView):
    """
    Return subscription statistics for an organization.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):

        # The organization is already protected by
        # IsOrganizationMember.
        subscription = get_object_or_404(
            Subscription.objects.select_related("plan"),
            organization_id=organization_id,
        )

        active_count = Subscription.objects.filter(
            organization_id=organization_id,
            status=Subscription.Status.ACTIVE,
        ).count()

        trialing_count = Subscription.objects.filter(
            organization_id=organization_id,
            status=Subscription.Status.TRIALING,
        ).count()

        past_due_count = Subscription.objects.filter(
            organization_id=organization_id,
            status=Subscription.Status.PAST_DUE,
        ).count()

        canceled_count = Subscription.objects.filter(
            organization_id=organization_id,
            status=Subscription.Status.CANCELED,
        ).count()

        return Response(
            {
                "organization_id": str(
                    organization_id
                ),
                "current_subscription": {
                    "plan": subscription.plan.code,
                    "status": subscription.status,
                    "interval": subscription.interval,
                },
                "subscriptions": {
                    "active": active_count,
                    "trialing": trialing_count,
                    "past_due": past_due_count,
                    "canceled": canceled_count,
                },
            },
            status=status.HTTP_200_OK,
        )


class RevenueTrendView(APIView):
    """
    Return monthly paid invoice revenue for an organization.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):

        # Make sure the organization has a subscription
        get_object_or_404(
            Subscription.objects.select_related("plan"),
            organization_id=organization_id,
        )

        trend = payment_trend(
            Payment.objects.filter(
                organization_id=organization_id,
            )
        )

        return Response(
            {
                "organization_id": str(organization_id),
                "currency": "USD",
                "trend": trend,
            },
            status=status.HTTP_200_OK,
        )


class ChurnView(APIView):
    """
    Return subscription churn metrics for an organization.

    Churn rate is calculated from the current subscription
    status snapshot:
        canceled / (active + trialing + past_due + canceled)
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):

        subscriptions = Subscription.objects.filter(
            organization_id=organization_id
        )

        active = subscriptions.filter(
            status=Subscription.Status.ACTIVE
        ).count()

        trialing = subscriptions.filter(
            status=Subscription.Status.TRIALING
        ).count()

        past_due = subscriptions.filter(
            status=Subscription.Status.PAST_DUE
        ).count()

        canceled = subscriptions.filter(
            status=Subscription.Status.CANCELED
        ).count()

        total = (
            active
            + trialing
            + past_due
            + canceled
        )

        churn_rate = (
            (canceled / total) * 100
            if total > 0
            else 0
        )

        return Response(
            {
                "organization_id": str(organization_id),
                "subscriptions": {
                    "active": active,
                    "trialing": trialing,
                    "past_due": past_due,
                    "canceled": canceled,
                    "total": total,
                },
                "churned": canceled,
                "churn_rate": round(churn_rate, 2),
            },
            status=status.HTTP_200_OK,
        )



class AnalyticsOverviewView(APIView):
    """
    Return a complete analytics overview for an organization.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):

        # -------------------------------------------------
        # Subscription data
        # -------------------------------------------------

        subscriptions = Subscription.objects.filter(
            organization_id=organization_id
        )

        active = subscriptions.filter(
            status=Subscription.Status.ACTIVE
        ).count()

        trialing = subscriptions.filter(
            status=Subscription.Status.TRIALING
        ).count()

        past_due = subscriptions.filter(
            status=Subscription.Status.PAST_DUE
        ).count()

        canceled = subscriptions.filter(
            status=Subscription.Status.CANCELED
        ).count()

        total_subscriptions = (
            active
            + trialing
            + past_due
            + canceled
        )

        # -------------------------------------------------
        # Churn
        # -------------------------------------------------

        churn_rate = (
            (canceled / total_subscriptions) * 100
            if total_subscriptions > 0
            else 0
        )

        # -------------------------------------------------
        # Current subscription / MRR
        # -------------------------------------------------

        current_subscription = (
            subscriptions
            .select_related("plan")
            .filter(
                status__in=[
                    Subscription.Status.ACTIVE,
                    Subscription.Status.TRIALING,
                    Subscription.Status.PAST_DUE,
                ]
            )
            .first()
        )

        mrr = Decimal("0.00")
        current_plan = None
        current_interval = None

        if current_subscription:
            current_plan = current_subscription.plan.code
            current_interval = current_subscription.interval
            mrr = monthly_value(current_subscription)

        # -------------------------------------------------
        # Money, kept strictly apart:
        # - customer payments: money THIS organization collected
        #   from its customers (invoice checkouts, manual payments)
        # - platform payments: money it paid the platform for its
        #   subscription (mirrored Stripe invoices)
        # A platform payment is the only kind that carries a
        # stripe_invoice_id.
        # -------------------------------------------------

        organization_payments = Payment.objects.filter(
            organization_id=organization_id,
        )

        def collected_total(payments):
            return (
                payments
                .filter(status__in=Payment.COLLECTED_STATUSES)
                .aggregate(total=Sum(NET_AMOUNT))["total"]
                or Decimal("0.00")
            )

        customer_payments = organization_payments.filter(
            stripe_invoice_id__isnull=True,
        )

        platform_payments = organization_payments.filter(
            stripe_invoice_id__isnull=False,
        )

        # The trend shows the business's own earnings, so platform
        # fees stay out of it.
        revenue_trend = payment_trend(customer_payments)

        collected_from_customers = collected_total(customer_payments)
        paid_to_platform = collected_total(platform_payments)
        total_paid = collected_from_customers + paid_to_platform

        # Customer invoices still waiting to be paid.
        open_invoices = (
            Invoice.objects
            .filter(
                organization_id=organization_id,
                status=Invoice.Status.OPEN,
                stripe_invoice_id__isnull=True,
            )
            .aggregate(count=Count("id"), amount=Sum("total"))
        )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------

        return Response(
            {
                "organization_id": str(organization_id),
                "currency": "USD",

                "mrr": f"{mrr:.2f}",

                "current_subscription": {
                    "plan": current_plan,
                    "interval": current_interval,
                },

                "active_subscriptions": active,

                "subscription_breakdown": {
                    "active": active,
                    "trialing": trialing,
                    "past_due": past_due,
                    "canceled": canceled,
                    "total": total_subscriptions,
                },

                "churn": {
                    "churned": canceled,
                    "churn_rate": round(churn_rate, 2),
                },

                "revenue_trend": revenue_trend,

                # Money the organization collected from its own
                # customers (invoice checkouts + manual payments).
                "collected_from_customers": (
                    f"{collected_from_customers:.2f}"
                ),

                # Subscription fees the organization paid the
                # platform (mirrored Stripe invoices).
                "paid_to_platform": f"{paid_to_platform:.2f}",

                # Customer invoices still waiting for payment.
                "open_invoices": {
                    "count": open_invoices["count"] or 0,
                    "amount": (
                        f"{open_invoices['amount'] or Decimal('0.00'):.2f}"
                    ),
                },

                # Kept for compatibility: everything combined.
                "total_paid": f"{total_paid:.2f}",
            },
            status=status.HTTP_200_OK,
        )

class PlatformOverviewView(APIView):
    """
    Business metrics for the PLATFORM OWNER across all organizations.
    Staff users only (Django ``is_staff``); organization members never
    see other organizations' data.

    MRR / ARR / ARPA come from current subscriptions (ACTIVE and
    TRIALING paid plans). Revenue comes from money actually received
    (Payment rows). Amounts are in USD; payments in other currencies
    are counted separately and not mixed into totals.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminUser,
    ]

    CHURN_WINDOW_DAYS = 30
    TREND_MONTHS = 12

    def get(self, request):
        now = timezone.now()

        subscriptions = list(
            Subscription.objects.select_related("plan")
        )

        # ---------------------------------------------------------
        # MRR by plan
        # ---------------------------------------------------------

        mrr = Decimal("0.00")
        paying = 0
        plans = {}

        for subscription in subscriptions:
            value = monthly_value(subscription)

            entry = plans.setdefault(
                subscription.plan.code,
                {"subscriptions": 0, "paying": 0, "mrr": Decimal("0.00")},
            )
            entry["subscriptions"] += 1

            if value > 0:
                paying += 1
                mrr += value
                entry["paying"] += 1
                entry["mrr"] += value

        # ---------------------------------------------------------
        # Status breakdown
        # ---------------------------------------------------------

        status_breakdown = {
            choice.value.lower(): 0
            for choice in Subscription.Status
        }

        for subscription in subscriptions:
            status_breakdown[subscription.status.lower()] += 1

        # ---------------------------------------------------------
        # Churn: paid subscriptions that ended in the last 30 days
        # (Stripe cancellation, or grace-period downgrade to FREE).
        # ---------------------------------------------------------

        churn_since = now - timedelta(days=self.CHURN_WINDOW_DAYS)

        churned = sum(
            1
            for subscription in subscriptions
            if subscription.canceled_at
            and subscription.canceled_at >= churn_since
            and monthly_value(subscription) == 0
        )

        churn_base = paying + churned

        churn_rate = (
            round(churned / churn_base * 100, 2)
            if churn_base
            else 0
        )

        # ---------------------------------------------------------
        # Revenue (money received)
        # ---------------------------------------------------------

        trend_since = (
            now - timedelta(days=31 * self.TREND_MONTHS)
        ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usd_payments = Payment.objects.filter(
            currency="USD",
            status__in=Payment.COLLECTED_STATUSES,
        )

        total_revenue = (
            usd_payments.aggregate(total=Sum(NET_AMOUNT))["total"]
            or Decimal("0.00")
        )

        revenue_by_method = {
            row["method"]: f"{row['total']:.2f}"
            for row in usd_payments
            .values("method")
            .annotate(total=Sum(NET_AMOUNT))
        }

        other_currency_payments = (
            Payment.objects
            .exclude(currency="USD")
            .filter(status__in=Payment.COLLECTED_STATUSES)
            .count()
        )

        return Response(
            {
                "currency": "USD",
                "organizations": Organization.objects.count(),
                "mrr": f"{mrr:.2f}",
                "arr": f"{mrr * 12:.2f}",
                "paying_subscriptions": paying,
                "arpa": (
                    f"{(mrr / paying):.2f}" if paying else "0.00"
                ),
                "plans": {
                    code: {
                        "subscriptions": entry["subscriptions"],
                        "paying": entry["paying"],
                        "mrr": f"{entry['mrr']:.2f}",
                    }
                    for code, entry in sorted(plans.items())
                },
                "subscription_status": status_breakdown,
                "churn": {
                    "window_days": self.CHURN_WINDOW_DAYS,
                    "churned": churned,
                    "churn_rate": churn_rate,
                },
                "revenue": {
                    "total": f"{total_revenue:.2f}",
                    "by_method": revenue_by_method,
                    "trend": payment_trend(
                        usd_payments.filter(paid_at__gte=trend_since)
                    ),
                    "other_currency_payments": other_currency_payments,
                },
            },
            status=status.HTTP_200_OK,
        )
