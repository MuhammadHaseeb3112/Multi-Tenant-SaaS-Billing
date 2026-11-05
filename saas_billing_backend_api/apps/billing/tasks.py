import logging

import stripe

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import (
    create_notification_for_organization_members,
)

from .models import Plan, Subscription


logger = logging.getLogger(__name__)


def cancel_stripe_subscription(stripe_subscription_id):
    """
    Cancel a Stripe subscription immediately.

    Returns True when the subscription is canceled in Stripe, or when
    Stripe reports it no longer exists / is already canceled (safe to
    treat as done). Returns False on any other Stripe error, so the
    caller can leave the local record untouched and retry later.
    """

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        stripe.Subscription.cancel(stripe_subscription_id)
        return True

    except stripe.error.InvalidRequestError as exc:
        # Already canceled or deleted in Stripe -> nothing left to stop.
        if getattr(exc, "code", None) == "resource_missing":
            return True

        message = str(exc).lower()

        if "canceled" in message or "cancelled" in message:
            return True

        logger.error(
            "Could not cancel Stripe subscription %s: %s",
            stripe_subscription_id,
            exc,
        )
        return False

    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe error while canceling subscription %s: %s",
            stripe_subscription_id,
            exc,
        )
        return False


@shared_task
def process_expired_grace_periods():
    """
    Downgrade subscriptions to FREE when their payment grace period
    has expired.

    The Stripe subscription is canceled FIRST. If that fails, the local
    subscription is left PAST_DUE and retried on the next run. Without
    this, Stripe would keep retrying the card and the next
    customer.subscription.updated webhook would switch the organization
    back to the paid plan.
    """

    now = timezone.now()

    free_plan = Plan.objects.filter(
        code="FREE",
        is_active=True,
    ).first()

    if free_plan is None:
        logger.error(
            "Grace period processing skipped: no active FREE plan."
        )
        return 0

    candidate_ids = list(
        Subscription.objects.filter(
            status=Subscription.Status.PAST_DUE,
            grace_period_end__isnull=False,
            grace_period_end__lte=now,
        ).values_list("id", flat=True)
    )

    processed_count = 0

    for subscription_id in candidate_ids:

        with transaction.atomic():

            # Re-check under a row lock: a payment webhook may have
            # resolved this subscription since the query above, and a
            # second worker must not process it twice.
            subscription = (
                Subscription.objects
                .select_for_update()
                .select_related("organization")
                .filter(
                    id=subscription_id,
                    status=Subscription.Status.PAST_DUE,
                    grace_period_end__lte=now,
                )
                .first()
            )

            if subscription is None:
                continue

            if subscription.stripe_subscription_id:
                canceled = cancel_stripe_subscription(
                    subscription.stripe_subscription_id
                )

                if not canceled:
                    continue

            subscription.plan = free_plan
            subscription.status = Subscription.Status.ACTIVE

            # The Stripe subscription is gone; clearing the ID lets the
            # organization start a fresh checkout later. The Stripe
            # customer is kept so it is reused.
            subscription.stripe_subscription_id = None
            subscription.cancel_at_period_end = False
            subscription.canceled_at = now

            subscription.payment_failed_at = None
            subscription.payment_retry_count = 0
            subscription.grace_period_end = None

            subscription.save(
                update_fields=[
                    "plan",
                    "status",
                    "stripe_subscription_id",
                    "cancel_at_period_end",
                    "canceled_at",
                    "payment_failed_at",
                    "payment_retry_count",
                    "grace_period_end",
                    "updated_at",
                ]
            )

            create_notification_for_organization_members(
                organization=subscription.organization,
                notification_type=(
                    Notification.NotificationType.SUBSCRIPTION_CANCELLED
                ),
                title="Downgraded to Free",
                message=(
                    "Your payment grace period has ended, so your "
                    "subscription was moved to the Free plan. You can "
                    "upgrade again at any time."
                ),
            )

            processed_count += 1

    return processed_count
