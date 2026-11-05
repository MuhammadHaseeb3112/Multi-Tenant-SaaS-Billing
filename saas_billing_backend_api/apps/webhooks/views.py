import json

import stripe

from apps.invoices.models import Invoice
from apps.invoices.payments import (
    mirror_paid_stripe_invoice,
    record_invoice_checkout_payment,
)
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import Plan, Subscription
from apps.tenants.models import Organization

from apps.notifications.models import Notification
from apps.notifications.services import (
    create_notification_for_organization_members,
)

from .models import WebhookEvent




class StripeWebhookView(APIView):
    """
    Stripe webhook endpoint.

    Responsibilities:
    - Verify Stripe webhook signature.
    - Store Stripe webhook events.
    - Prevent duplicate processing.
    - Synchronize local subscription state with Stripe.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        # ---------------------------------------------------------
        # 1. Get raw request body
        # ---------------------------------------------------------
        payload = request.body

        signature = request.META.get("HTTP_STRIPE_SIGNATURE")

        if not signature:
            return Response(
                {"detail": "Missing Stripe signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 2. Verify Stripe signature
        # ---------------------------------------------------------
        try:
            stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )

        except ValueError:
            return Response(
                {"detail": "Invalid webhook payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except stripe.error.SignatureVerificationError:
            return Response(
                {"detail": "Invalid Stripe signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 3. Convert verified webhook JSON into normal dict
        # ---------------------------------------------------------
        try:
            event = json.loads(payload.decode("utf-8"))

        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                {"detail": "Invalid webhook JSON payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_id = event.get("id")
        event_type = event.get("type")

        if not event_id:
            return Response(
                {"detail": "Webhook event is missing an event ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not event_type:
            return Response(
                {"detail": "Webhook event is missing an event type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 4. Store webhook event
        # ---------------------------------------------------------
        webhook_event, created = WebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload": event,
            },
        )

        # ---------------------------------------------------------
        # 5. Idempotency
        # ---------------------------------------------------------
        if not created and webhook_event.processed:
            return Response(
                {"detail": "Webhook already processed."},
                status=status.HTTP_200_OK,
            )

        # ---------------------------------------------------------
        # 6. Process webhook
        # ---------------------------------------------------------
        try:
            with transaction.atomic():
                self.handle_event(event)

                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.error_message = ""

                webhook_event.save(
                    update_fields=[
                        "processed",
                        "processed_at",
                        "error_message",
                    ]
                )

        except Exception as exc:
            webhook_event.error_message = str(exc)

            webhook_event.save(
                update_fields=[
                    "error_message",
                ]
            )

            raise

        return Response(
            {"detail": "Webhook processed successfully."},
            status=status.HTTP_200_OK,
        )

    # =============================================================
    # EVENT ROUTER
    # =============================================================

    def handle_event(self, event):
        """
        Route Stripe events to the appropriate handler.
        """

        event_type = event.get("type")

        handlers = {
            "checkout.session.completed": self.handle_checkout_completed,
            "checkout.session.async_payment_succeeded": self.handle_checkout_completed,
            "invoice.payment_succeeded": self.handle_invoice_payment_succeeded,
            # Stripe sends invoice.paid alongside payment_succeeded (and
            # also for invoices paid out of band). Only mirrors the
            # invoice; idempotent, so receiving both is safe.
            "invoice.paid": self.handle_invoice_paid,
            # Draft renewal invoice: add last period's usage overage.
            "invoice.created": self.handle_invoice_created,
            "invoice.payment_failed": self.handle_invoice_payment_failed,
            "customer.subscription.updated": self.handle_subscription_updated,
            "customer.subscription.deleted": self.handle_subscription_deleted,
        }

        handler = handlers.get(event_type)

        if handler:
            handler(event)

        # Unsupported events are intentionally ignored.
        # They are still stored and marked as processed.

    # =============================================================
    # CHECKOUT SESSION COMPLETED
    # =============================================================

    def handle_checkout_completed(self, event):
        """
        Handle Stripe Checkout completion.

        Supports both:
        1. SaaS subscription checkout
        2. One-time invoice payment checkout
        """

        session = event["data"]["object"]

        metadata = session.get("metadata") or {}

        # =========================================================
        # INVOICE PAYMENT
        # =========================================================

        if metadata.get("payment_type") == "invoice":
            self.handle_invoice_checkout_completed(session)
            return

        # =========================================================
        # EXISTING SAAS SUBSCRIPTION CHECKOUT
        # =========================================================

        # client_reference_id is set by our checkout endpoint as a
        # second, independent copy of the organization ID.
        organization_id = (
            metadata.get("organization_id")
            or session.get("client_reference_id")
        )

        stripe_customer_id = self.extract_stripe_id(
            session.get("customer")
        )
        stripe_subscription_id = self.extract_stripe_id(
            session.get("subscription")
        )

        # ---------------------------------------------------------
        # Validate required data
        # ---------------------------------------------------------

        if not organization_id:
            raise ValueError(
                "Checkout session is missing organization_id metadata "
                "and client_reference_id. It was probably not created "
                "by this application (for example `stripe trigger`)."
            )

        if not stripe_subscription_id:
            raise ValueError(
                "Checkout session is missing Stripe subscription ID."
            )

        # ---------------------------------------------------------
        # Find organization
        # ---------------------------------------------------------

        organization = Organization.objects.get(
            id=organization_id
        )

        # ---------------------------------------------------------
        # Never silently replace a different live Stripe subscription
        # ---------------------------------------------------------
        #
        # Overwriting would orphan the old Stripe subscription, which
        # would keep charging the customer. Fail loudly instead; the
        # event stays unprocessed with this error for manual review.

        existing_subscription = (
            Subscription.objects
            .select_for_update()
            .filter(organization=organization)
            .first()
        )

        if (
            existing_subscription
            and existing_subscription.stripe_subscription_id
            and existing_subscription.stripe_subscription_id
            != stripe_subscription_id
            and existing_subscription.status
            != Subscription.Status.CANCELED
        ):
            raise ValueError(
                f"Organization {organization.id} is already linked to "
                f"Stripe subscription "
                f"{existing_subscription.stripe_subscription_id}; "
                f"refusing to overwrite it with "
                f"{stripe_subscription_id}. Cancel one of them in "
                f"Stripe, then reprocess this event."
            )

        # ---------------------------------------------------------
        # Retrieve current subscription from Stripe
        # ---------------------------------------------------------

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe_subscription = stripe.Subscription.retrieve(
            stripe_subscription_id
        ).to_dict()

        # ---------------------------------------------------------
        # Plan and interval come from the Stripe price (source of
        # truth), not from metadata typed in at checkout time.
        # ---------------------------------------------------------

        plan, interval = self.get_plan_from_stripe_subscription(
            stripe_subscription
        )

        # ---------------------------------------------------------
        # Get billing period
        # ---------------------------------------------------------

        current_period_start, current_period_end = (
            self.get_subscription_period(
                stripe_subscription
            )
        )

        # ---------------------------------------------------------
        # Map Stripe status
        # ---------------------------------------------------------

        subscription_status = self.map_stripe_subscription_status(
            stripe_subscription.get("status")
        )

        # ---------------------------------------------------------
        # Save local subscription
        # ---------------------------------------------------------

        Subscription.objects.update_or_create(
            organization=organization,
            defaults={
                "plan": plan,
                "status": subscription_status,
                "interval": interval,
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "stripe_customer_id": self.extract_stripe_id(
                    stripe_customer_id
                ),
                "stripe_subscription_id": self.extract_stripe_id(
                    stripe_subscription_id
                ),
                "cancel_at_period_end": stripe_subscription.get(
                    "cancel_at_period_end",
                    False,
                ),
                "canceled_at": self.timestamp_to_datetime(
                    stripe_subscription.get("canceled_at")
                ),
            },
        )


    def handle_invoice_checkout_completed(self, session):
        """
        Mark a local invoice as PAID after successful Stripe Checkout.
        """

        metadata = session.get("metadata") or {}

        invoice_id = metadata.get("invoice_id")
        organization_id = metadata.get("organization_id")

        if not invoice_id:
            raise ValueError(
                "Invoice payment Checkout session is missing invoice_id."
            )

        if not organization_id:
            raise ValueError(
                "Invoice payment Checkout session is missing organization_id."
            )

        # For checkout.session.completed, verify Stripe says
        # the payment is actually paid.
        payment_status = session.get("payment_status")

        if payment_status != "paid":
            return

        invoice = Invoice.objects.filter(
            id=invoice_id,
            organization_id=organization_id,
        ).first()

        if not invoice:
            raise ValueError(
                f"Invoice {invoice_id} does not exist."
            )

        # Already PAID (replayed event, or marked paid manually before
        # the card payment landed): the money from THIS checkout was
        # still received, so make sure it is recorded (idempotent on
        # the session ID), but do not change the invoice again.
        if invoice.status == Invoice.Status.PAID:
            record_invoice_checkout_payment(session, invoice)
            return

        # Only OPEN invoices can become PAID.
        if invoice.status != Invoice.Status.OPEN:
            raise ValueError(
                f"Invoice {invoice.invoice_number} cannot be marked "
                f"as paid from status {invoice.status}."
            )

        invoice.status = Invoice.Status.PAID
        invoice.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        record_invoice_checkout_payment(session, invoice)


    # =============================================================
    # INVOICE PAYMENT SUCCEEDED
    # =============================================================

    def handle_invoice_payment_succeeded(self, event):
        """
        Handle successful recurring invoice payment.
        """

        invoice = event["data"]["object"]

        stripe_subscription_id = self.get_invoice_subscription_id(
            invoice
        )

        if not stripe_subscription_id:
            return

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first()

        if not subscription:
            return

        # Record the paid invoice and the money received locally.
        mirror_paid_stripe_invoice(
            invoice,
            subscription.organization,
        )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe_subscription = stripe.Subscription.retrieve(
            stripe_subscription_id
        ).to_dict()

        current_period_start, current_period_end = (
            self.get_subscription_period(stripe_subscription)
        )

        subscription.status = self.map_stripe_subscription_status(
            stripe_subscription.get("status")
        )

        subscription.current_period_start = current_period_start
        subscription.current_period_end = current_period_end

        subscription.payment_failed_at = None
        subscription.payment_retry_count = 0
        subscription.grace_period_end = None

        subscription.save(
            update_fields=[
                "status",
                "current_period_start",
                "current_period_end",
                "payment_failed_at",
                "payment_retry_count",
                "grace_period_end",
                "updated_at",
            ]
        )

        create_notification_for_organization_members(
            organization=subscription.organization,
            notification_type=Notification.NotificationType.PAYMENT_SUCCESS,
            title="Payment Successful",
            message="Your subscription payment was successfully processed.",
        )

    # =============================================================
    # INVOICE PAID
    # =============================================================

    def handle_invoice_paid(self, event):
        """
        Mirror a paid Stripe invoice into the local database.

        No subscription changes or notifications here: those belong to
        invoice.payment_succeeded, which Stripe sends for the same
        payment.
        """

        invoice = event["data"]["object"]

        organization = self.get_invoice_organization(invoice)

        if organization is None:
            return

        mirror_paid_stripe_invoice(invoice, organization)

    def handle_invoice_created(self, event):
        """
        Stripe created a (draft) invoice. For subscription renewals,
        bill the usage overage of the period that just closed by adding
        an invoice item to this draft (see apps/usage/overage.py).

        A Stripe error raises, so the event stays unprocessed and is
        retried; billing is idempotent per subscription + period.
        """

        from apps.usage.overage import bill_overage_for_invoice

        invoice = event["data"]["object"]

        stripe_subscription_id = self.get_invoice_subscription_id(
            invoice
        )

        if not stripe_subscription_id:
            return

        subscription = (
            Subscription.objects
            .select_related("plan")
            .filter(stripe_subscription_id=stripe_subscription_id)
            .first()
        )

        if subscription is None:
            return

        bill_overage_for_invoice(subscription, invoice)

    def get_invoice_organization(self, invoice):
        """
        Find the organization a Stripe invoice belongs to: first via
        the local subscription, then via the organization_id metadata
        that checkout copies onto the Stripe subscription.
        """

        stripe_subscription_id = self.get_invoice_subscription_id(
            invoice
        )

        if stripe_subscription_id:
            subscription = (
                Subscription.objects
                .select_related("organization")
                .filter(stripe_subscription_id=stripe_subscription_id)
                .first()
            )

            if subscription:
                return subscription.organization

        parent = invoice.get("parent") or {}
        details = parent.get("subscription_details") or {}
        metadata = details.get("metadata") or {}

        organization_id = metadata.get("organization_id")

        if organization_id:
            return Organization.objects.filter(
                id=organization_id
            ).first()

        return None

    # =============================================================
    # INVOICE PAYMENT FAILED
    # =============================================================

    def handle_invoice_payment_failed(self, event):
        """
        Handle failed recurring invoice payment.

        Stripe remains responsible for payment retries.
        We track the local dunning state.
        """

        invoice = event["data"]["object"]

        stripe_subscription_id = self.get_invoice_subscription_id(
            invoice
        )

        if not stripe_subscription_id:
            return

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first()

        if not subscription:
            return

        # Stripe invoice attempt count.
        attempt_count = invoice.get("attempt_count") or 1

        # Use the first failed payment as the beginning
        # of our local dunning period.
        if not subscription.payment_failed_at:
            subscription.payment_failed_at = timezone.now()

        subscription.payment_retry_count = attempt_count

        # ---------------------------------------------------------
        # Grace period
        # ---------------------------------------------------------
        #
        # For now we use a 7-day grace period.
        # Celery will later enforce the final downgrade.
        #
        if not subscription.grace_period_end:
            subscription.grace_period_end = (
                timezone.now() + timedelta(days=7)
            )

        subscription.status = Subscription.Status.PAST_DUE

        subscription.save(
            update_fields=[
                "status",
                "payment_failed_at",
                "payment_retry_count",
                "grace_period_end",
                "updated_at",
            ]
        )

        create_notification_for_organization_members(
            organization=subscription.organization,
            notification_type=Notification.NotificationType.PAYMENT_FAILED,
            title="Payment Failed",
            message=(
                "Your subscription payment failed. "
                "Please update your payment method to avoid service interruption."
            ),
        )

    @staticmethod
    def get_plan_from_stripe_subscription(stripe_subscription):
        """
        Determine the local plan and billing interval from
        the Stripe subscription's current price.
        """

        items = stripe_subscription.get("items") or {}
        data = items.get("data") or []

        if not data:
            raise ValueError(
                "Stripe subscription has no subscription items."
            )

        first_item = data[0]

        price = first_item.get("price") or {}
        price_id = price.get("id")

        if not price_id:
            raise ValueError(
                "Stripe subscription item is missing price ID."
            )

        plan = Plan.objects.filter(
            stripe_monthly_price_id=price_id,
            is_active=True,
        ).first()

        if plan:
            return plan, Subscription.Interval.MONTHLY

        plan = Plan.objects.filter(
            stripe_annual_price_id=price_id,
            is_active=True,
        ).first()

        if plan:
            return plan, Subscription.Interval.ANNUAL

        raise ValueError(
            f"No active local plan is configured for Stripe price "
            f"{price_id}."
        )

    # =============================================================
    # CUSTOMER SUBSCRIPTION UPDATED
    # =============================================================

    def handle_subscription_updated(self, event):
        """
        Synchronize the local subscription with the current
        Stripe subscription state.

        We retrieve the subscription directly from Stripe instead
        of relying entirely on the webhook payload. This prevents
        stale/out-of-order webhook events from overwriting newer
        subscription state.
        """

        event_subscription = event["data"]["object"]

        stripe_subscription_id = self.extract_stripe_id(
            event_subscription.get("id")
        )

        if not stripe_subscription_id:
            raise ValueError(
                "Stripe subscription update is missing subscription ID."
            )

        # ---------------------------------------------------------
        # Find local subscription
        # ---------------------------------------------------------

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first()

        if not subscription:
            return

        # ---------------------------------------------------------
        # Retrieve the CURRENT subscription from Stripe
        # ---------------------------------------------------------

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe_subscription = (
            stripe.Subscription.retrieve(
                stripe_subscription_id
            ).to_dict()
        )

        # ---------------------------------------------------------
        # Determine current local plan and interval
        # ---------------------------------------------------------

        plan, interval = self.get_plan_from_stripe_subscription(
            stripe_subscription
        )

        # ---------------------------------------------------------
        # Get current billing period
        # ---------------------------------------------------------

        current_period_start, current_period_end = (
            self.get_subscription_period(
                stripe_subscription
            )
        )

        # ---------------------------------------------------------
        # Synchronize local subscription
        # ---------------------------------------------------------

        subscription.plan = plan

        subscription.interval = interval

        subscription.status = (
            self.map_stripe_subscription_status(
                stripe_subscription.get("status")
            )
        )

        subscription.cancel_at_period_end = (
            stripe_subscription.get(
                "cancel_at_period_end",
                False,
            )
        )

        subscription.canceled_at = (
            self.timestamp_to_datetime(
                stripe_subscription.get("canceled_at")
            )
        )

        subscription.current_period_start = (
            current_period_start
        )

        subscription.current_period_end = (
            current_period_end
        )

        subscription.save(
            update_fields=[
                "plan",
                "interval",
                "status",
                "cancel_at_period_end",
                "canceled_at",
                "current_period_start",
                "current_period_end",
                "updated_at",
            ]
        )

        create_notification_for_organization_members(
            organization=subscription.organization,
            notification_type=Notification.NotificationType.SUBSCRIPTION_UPDATED,
            title="Subscription Updated",
            message=(
                f"Your subscription has been updated to "
                f"{subscription.plan.name} ({subscription.interval.lower()})."
            ),
        )

    # =============================================================
    # CUSTOMER SUBSCRIPTION DELETED
    # =============================================================

    def handle_subscription_deleted(self, event):
        """
        Handle a deleted/canceled Stripe subscription.
        """

        stripe_subscription = event["data"]["object"]

        stripe_subscription_id = self.extract_stripe_id(
            stripe_subscription.get("id")
        )

        if not stripe_subscription_id:
            raise ValueError(
                "Deleted Stripe subscription is missing subscription ID."
            )

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first()

        if not subscription:
            return

        subscription.status = Subscription.Status.CANCELED
        subscription.canceled_at = timezone.now()
        subscription.cancel_at_period_end = False

        subscription.save(
            update_fields=[
                "status",
                "canceled_at",
                "cancel_at_period_end",
                "updated_at",
            ]
        )

        create_notification_for_organization_members(
            organization=subscription.organization,
            notification_type=Notification.NotificationType.SUBSCRIPTION_CANCELLED,
            title="Subscription Cancelled",
            message="Your subscription has been cancelled.",
        )

    # =============================================================
    # HELPERS
    # =============================================================

    @staticmethod
    def get_subscription_period(subscription):
        """
        Get the current billing period from the first
        Stripe subscription item.

        Stripe API 2025-03-31+ stores billing periods
        on subscription items instead of the top-level
        subscription object.
        """

        items = subscription.get("items") or {}
        data = items.get("data") or []

        if not data:
            return None, None

        first_item = data[0]

        return (
            StripeWebhookView.timestamp_to_datetime(
                first_item.get("current_period_start")
            ),
            StripeWebhookView.timestamp_to_datetime(
                first_item.get("current_period_end")
            ),
        )

    @staticmethod
    def map_stripe_subscription_status(stripe_status):
        """
        Convert Stripe subscription status into our local status.
        """

        status_map = {
            "trialing": Subscription.Status.TRIALING,
            "active": Subscription.Status.ACTIVE,
            "past_due": Subscription.Status.PAST_DUE,
            "canceled": Subscription.Status.CANCELED,
            "unpaid": Subscription.Status.UNPAID,
        }

        subscription_status = status_map.get(
            stripe_status
        )

        if subscription_status is None:
            raise ValueError(
                f"Unsupported Stripe subscription status: "
                f"{stripe_status}"
            )

        return subscription_status

    @staticmethod
    def timestamp_to_datetime(timestamp):
        """
        Convert Stripe Unix timestamp into a timezone-aware
        Django datetime.
        """

        if timestamp is None:
            return None

        return timezone.datetime.fromtimestamp(
            timestamp,
            tz=timezone.get_current_timezone(),
        )

    @staticmethod
    def get_invoice_subscription_id(invoice):
        """
        Find the Stripe subscription ID that an invoice belongs to.

        Stripe API 2025-03-31 (basil) and newer removed the top-level
        ``invoice.subscription`` field. The subscription now lives at
        ``invoice.parent.subscription_details.subscription``, and on
        each line item at
        ``lines.data[].parent.subscription_item_details.subscription``.

        Older payloads are still supported so that previously stored
        events can be reprocessed safely.
        """

        extract = StripeWebhookView.extract_stripe_id

        # 1. Legacy API versions (before 2025-03-31).
        legacy_id = extract(invoice.get("subscription"))

        if legacy_id:
            return legacy_id

        # 2. Current API: invoice.parent.subscription_details.subscription
        parent = invoice.get("parent") or {}
        subscription_details = (
            parent.get("subscription_details") or {}
        )

        parent_id = extract(
            subscription_details.get("subscription")
        )

        if parent_id:
            return parent_id

        # 3. Fallback: the first line item that references a subscription.
        lines = invoice.get("lines") or {}

        for line in lines.get("data") or []:
            line_parent = line.get("parent") or {}
            item_details = (
                line_parent.get("subscription_item_details") or {}
            )

            line_id = extract(item_details.get("subscription"))

            if line_id:
                return line_id

        return None

    @staticmethod
    def extract_stripe_id(value):
        """
        Extract an ID from a Stripe ID string or an expanded
        Stripe object represented as a dictionary.

        Examples:
            "sub_123" -> "sub_123"
            {"id": "sub_123"} -> "sub_123"
            None -> None
        """

        if value is None:
            return None

        if isinstance(value, dict):
            return value.get("id")

        return str(value)


