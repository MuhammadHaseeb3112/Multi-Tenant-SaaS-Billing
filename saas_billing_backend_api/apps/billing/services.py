import stripe

from django.conf import settings

from .models import Subscription


class SubscriptionChangeError(Exception):
    """Raised when a subscription change cannot be completed."""


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

    updated_subscription = stripe.Subscription.modify(
        subscription.stripe_subscription_id,
        items=[
            {
                "id": current_item["id"],
                "price": price_id,
            }
        ],
        proration_behavior="create_prorations",
    )

    # Convert StripeObject → normal dict
    return updated_subscription.to_dict()