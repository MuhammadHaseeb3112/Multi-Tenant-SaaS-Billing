import stripe

from django.conf import settings

from .models import Subscription


class SubscriptionChangeError(Exception):
    """Raised when a subscription change cannot be completed."""


class SubscriptionPaymentError(SubscriptionChangeError):
    """
    Raised when an upgrade's charge fails. The plan is NOT changed:
    the customer keeps the current plan until an upgrade is paid for.
    """


def monthly_cost(plan, interval):
    """Price of a plan per month, so plans and intervals compare."""

    if interval == Subscription.Interval.ANNUAL:
        return plan.annual_price / 12

    return plan.monthly_price


def is_upgrade(subscription, new_plan, new_interval):
    """
    An upgrade costs more per month, or moves monthly -> annual (Stripe
    bills a new annual period at once). Upgrades are paid up front;
    everything else is a downgrade that takes effect with a credit.
    """

    if (
        subscription.interval == Subscription.Interval.MONTHLY
        and new_interval == Subscription.Interval.ANNUAL
    ):
        return True

    return monthly_cost(new_plan, new_interval) > monthly_cost(
        subscription.plan,
        subscription.interval,
    )


def change_stripe_subscription(
    subscription,
    new_plan,
    new_interval,
):
    """
    Change an existing Stripe subscription to a new price.

    Stripe remains the source of truth for the subscription change.
    The webhook synchronizes the local database afterward.
    """

    if not subscription.stripe_subscription_id:
        raise SubscriptionChangeError(
            "This organization does not have an active Stripe subscription."
        )

    # ---------------------------------------------------------
    # Select Stripe price
    # ---------------------------------------------------------

    if new_interval == Subscription.Interval.MONTHLY:
        price_id = new_plan.stripe_monthly_price_id

    elif new_interval == Subscription.Interval.ANNUAL:
        price_id = new_plan.stripe_annual_price_id

    else:
        raise SubscriptionChangeError(
            "Invalid subscription interval."
        )

    if not price_id:
        raise SubscriptionChangeError(
            f"No Stripe price is configured for "
            f"{new_plan.code} {new_interval}."
        )

    # ---------------------------------------------------------
    # Stripe configuration
    # ---------------------------------------------------------

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # ---------------------------------------------------------
    # Retrieve current Stripe subscription
    # ---------------------------------------------------------

    stripe_subscription = stripe.Subscription.retrieve(
        subscription.stripe_subscription_id
    ).to_dict()

    # ---------------------------------------------------------
    # Get current subscription item
    # ---------------------------------------------------------

    items = stripe_subscription.get("items") or {}
    data = items.get("data") or []

    if not data:
        raise SubscriptionChangeError(
            "Stripe subscription has no subscription items."
        )

    current_item = data[0]

    # ---------------------------------------------------------
    # Get current price ID
    # ---------------------------------------------------------

    current_price = current_item.get("price") or {}

    current_price_id = current_price.get("id")

    # ---------------------------------------------------------
    # Prevent unnecessary Stripe API call
    # ---------------------------------------------------------

    if current_price_id == price_id:
        raise SubscriptionChangeError(
            "The subscription is already using this plan and interval."
        )

    # ---------------------------------------------------------
    # Update Stripe subscription
    # ---------------------------------------------------------

    items = [
        {
            "id": current_item["id"],
            "price": price_id,
        }
    ]

    if not is_upgrade(subscription, new_plan, new_interval):
        # Downgrade: switch now; the unused part of the current plan
        # becomes a credit on the next invoice. Nothing to charge.
        updated_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=items,
            proration_behavior="create_prorations",
        )

        return updated_subscription.to_dict()

    # Upgrade: charge the prorated difference right now, and apply the
    # new plan ONLY if that payment succeeds. With pending_if_incomplete
    # a declined card leaves the subscription untouched and parks the
    # change in `pending_update` instead of granting the plan unpaid.
    updated_subscription = stripe.Subscription.modify(
        subscription.stripe_subscription_id,
        items=items,
        proration_behavior="always_invoice",
        payment_behavior="pending_if_incomplete",
    ).to_dict()

    if updated_subscription.get("pending_update"):
        cancel_pending_update(updated_subscription)

        raise SubscriptionPaymentError(
            "Your payment for the upgrade failed, so your plan was not "
            "changed. Please update your payment method and try again."
        )

    return updated_subscription


def cancel_pending_update(stripe_subscription):
    """
    Drop a failed upgrade at once instead of leaving it pending for 23h:
    voiding the invoice the update created discards the update.
    """

    invoice_id = stripe_subscription.get("latest_invoice")

    if isinstance(invoice_id, dict):
        invoice_id = invoice_id.get("id")

    if not invoice_id:
        return

    try:
        stripe.Invoice.void_invoice(invoice_id)

    except stripe.error.StripeError:
        # Stripe voids it itself when the pending update expires.
        pass