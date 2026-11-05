"""
Billing of usage overage at the end of a billing period.

Flow (normal case):
    Stripe renews a subscription -> creates a DRAFT renewal invoice
    (billing_reason = "subscription_cycle") and sends ``invoice.created``.
    Our webhook calls ``bill_overage_for_invoice`` which counts the usage
    in the closed period (invoice.period_start .. invoice.period_end) and,
    if the org went over its plan limit, adds ONE invoice item for the
    overage to that draft invoice. Stripe then finalizes and charges it
    together with the next period's subscription fee.

Safety:
    - One ``OverageCharge`` per (subscription, period_start) (DB unique).
    - Deterministic Stripe idempotency key per subscription + period, so
      a retried webhook can never create a second invoice item.
"""

from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from .models import OverageCharge, UsageRecord
from .services import calculate_overage_amount



def _from_timestamp(value):
    return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)


def usage_in_window(organization_id, start, end):
    return (
        UsageRecord.objects
        .filter(
            organization_id=organization_id,
            resource=UsageRecord.ResourceType.API_REQUEST,
            recorded_at__gte=start,
            recorded_at__lt=end,
        )
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )


def calculate_period_overage(subscription, start, end):
    """
    Return ``(used, included, overage, price_per_1000, amount)`` for the
    window, using the subscription's current plan.
    """

    plan = subscription.plan
    used = usage_in_window(subscription.organization_id, start, end)
    included = plan.api_request_limit
    overage = max(used - included, 0)
    price = plan.overage_price_per_1000
    amount = calculate_overage_amount(overage, price)

    return used, included, overage, price, amount


def idempotency_key(subscription, start):
    return f"overage-{subscription.id}-{int(start.timestamp())}"


def bill_overage(
    *,
    subscription,
    period_start,
    period_end,
    currency="usd",
    stripe_invoice_id=None,
):
    """
    Bill the overage of one closed period. Idempotent.

    With ``stripe_invoice_id`` the item is attached to that draft invoice
    (status BILLED). Without it, it becomes a pending invoice item that
    Stripe puts on the subscription's next invoice
    (status PENDING_NEXT_INVOICE).

    Returns the ``OverageCharge`` (existing or new), or ``None`` when
    there is nothing to bill.
    """

    existing = OverageCharge.objects.filter(
        subscription=subscription,
        period_start=period_start,
    ).first()

    if existing:
        return existing

    used, included, overage, price, amount = calculate_period_overage(
        subscription, period_start, period_end
    )

    if overage <= 0 or amount <= 0:
        return None

    if not subscription.stripe_customer_id:
        raise ValueError(
            "Cannot bill overage: subscription has no Stripe customer."
        )

    currency = (currency or "usd").lower()
    amount_cents = int(amount * 100)

    params = {
        "customer": subscription.stripe_customer_id,
        "amount": amount_cents,
        "currency": currency,
        "description": (
            f"API overage: {overage:,} requests over the "
            f"{included:,} included ({price}/1,000)"
        ),
        "period": {
            "start": int(period_start.timestamp()),
            "end": int(period_end.timestamp()),
        },
        "metadata": {
            "type": "usage_overage",
            "organization_id": str(subscription.organization_id),
            "subscription_id": str(subscription.id),
            "overage_requests": str(overage),
        },
    }

    if stripe_invoice_id:
        params["invoice"] = stripe_invoice_id
    elif subscription.stripe_subscription_id:
        params["subscription"] = subscription.stripe_subscription_id

    stripe.api_key = settings.STRIPE_SECRET_KEY

    invoice_item = stripe.InvoiceItem.create(
        idempotency_key=idempotency_key(subscription, period_start),
        **params,
    )

    with transaction.atomic():
        return OverageCharge.objects.create(
            organization_id=subscription.organization_id,
            subscription=subscription,
            period_start=period_start,
            period_end=period_end,
            included_requests=included,
            used_requests=used,
            overage_requests=overage,
            price_per_1000=price,
            amount=amount,
            currency=currency,
            status=(
                OverageCharge.Status.BILLED
                if stripe_invoice_id
                else OverageCharge.Status.PENDING_NEXT_INVOICE
            ),
            stripe_invoice_id=stripe_invoice_id or "",
            stripe_invoice_item_id=invoice_item["id"],
        )


def bill_overage_for_invoice(subscription, invoice):
    """
    Called from the ``invoice.created`` webhook with the Stripe invoice
    dict. Only renewal invoices that are still drafts are handled.
    """

    if invoice.get("billing_reason") != "subscription_cycle":
        return None

    if invoice.get("status") != "draft":
        return None

    period_start = invoice.get("period_start")
    period_end = invoice.get("period_end")

    if not period_start or not period_end or period_start >= period_end:
        return None

    return bill_overage(
        subscription=subscription,
        period_start=_from_timestamp(period_start),
        period_end=_from_timestamp(period_end),
        currency=invoice.get("currency") or "usd",
        stripe_invoice_id=invoice.get("id"),
    )
