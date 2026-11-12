

import json
from unittest.mock import patch

import stripe
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase

from apps.billing.models import Plan, Subscription
from apps.tenants.models import Organization
from apps.webhooks.views import StripeWebhookView


class StripeSubscriptionPlanMappingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            stripe_monthly_price_id="price_enterprise_monthly_test",
            stripe_annual_price_id="price_enterprise_annual_test",
        )

        cls.pro_plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            stripe_monthly_price_id="price_pro_monthly_test",
            stripe_annual_price_id="price_pro_annual_test",
        )

        cls.webhook_view = StripeWebhookView()

    def test_pro_annual_price_maps_to_pro_annual(self):
        stripe_subscription = {
            "items": {
                "data": [
                    {"price": {"id": "price_pro_annual_test"}}
                ]
            }
        }

        plan, interval = (
            self.webhook_view.get_plan_from_stripe_subscription(
                stripe_subscription
            )
        )

        self.assertEqual(plan, self.pro_plan)
        self.assertEqual(interval, Subscription.Interval.ANNUAL)

    def test_enterprise_monthly_price_maps_correctly(self):
        stripe_subscription = {
            "items": {
                "data": [
                    {"price": {"id": "price_enterprise_monthly_test"}}
                ]
            }
        }

        plan, interval = (
            self.webhook_view.get_plan_from_stripe_subscription(
                stripe_subscription
            )
        )

        self.assertEqual(plan, self.enterprise_plan)
        self.assertEqual(interval, Subscription.Interval.MONTHLY)

    def test_unknown_price_raises_value_error(self):
        stripe_subscription = {
            "items": {
                "data": [
                    {"price": {"id": "price_unknown_test"}}
                ]
            }
        }

        with self.assertRaisesMessage(
            ValueError,
            "No active local plan is configured for Stripe price",
        ):
            self.webhook_view.get_plan_from_stripe_subscription(
                stripe_subscription
            )


class StripeSubscriptionUpdateTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Webhook Test Organization"
        )

        self.pro_plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            stripe_monthly_price_id="price_pro_monthly_test",
            stripe_annual_price_id="price_pro_annual_test",
        )

        self.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            stripe_monthly_price_id="price_enterprise_monthly_test",
            stripe_annual_price_id="price_enterprise_annual_test",
        )

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.enterprise_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            stripe_subscription_id="sub_webhook_update_test",
        )

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_update_syncs_plan_interval_status_and_period(
        self,
        mock_retrieve,
        mock_notification,
    ):
        start_timestamp = 1798932600
        end_timestamp = 1830468600

        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_webhook_update_test",
            "status": "active",
            "cancel_at_period_end": False,
            "canceled_at": None,
            "items": {
                "data": [
                    {
                        "price": {"id": "price_pro_annual_test"},
                        "current_period_start": start_timestamp,
                        "current_period_end": end_timestamp,
                    }
                ]
            },
        }

        event = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {"id": "sub_webhook_update_test"}
            },
        }

        self.webhook_view = StripeWebhookView()
        self.webhook_view.handle_subscription_updated(event)

        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.plan, self.pro_plan)
        self.assertEqual(
            self.subscription.interval,
            Subscription.Interval.ANNUAL,
        )
        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )
        self.assertFalse(self.subscription.cancel_at_period_end)
        self.assertEqual(
            self.subscription.current_period_start,
            datetime.fromtimestamp(
                start_timestamp, tz=datetime_timezone.utc
            ),
        )
        self.assertEqual(
            self.subscription.current_period_end,
            datetime.fromtimestamp(
                end_timestamp, tz=datetime_timezone.utc
            ),
        )

        mock_retrieve.assert_called_once_with(
            "sub_webhook_update_test"
        )
        mock_notification.assert_called_once()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_update_without_plan_change_does_not_notify(
        self,
        mock_retrieve,
        mock_notification,
    ):
        # Same plan and interval as the local subscription (e.g. the
        # card was changed or an upgrade payment failed).
        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_webhook_update_test",
            "status": "active",
            "cancel_at_period_end": True,
            "canceled_at": None,
            "items": {
                "data": [
                    {
                        "price": {"id": "price_enterprise_monthly_test"},
                        "current_period_start": 1798932600,
                        "current_period_end": 1830468600,
                    }
                ]
            },
        }

        StripeWebhookView().handle_subscription_updated({
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_webhook_update_test"}},
        })

        self.subscription.refresh_from_db()

        # Still synchronized...
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertEqual(self.subscription.plan, self.enterprise_plan)
        # ...but nobody is told the plan "was updated".
        mock_notification.assert_not_called()


class StripeWebhookEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("stripe-webhook")

    def test_missing_signature_returns_400(self):
        response = self.client.post(
            self.url,
            data=b'{"id":"evt_missing_signature","type":"test.event"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Missing Stripe signature.",
        )

    @patch("apps.webhooks.views.stripe.Webhook.construct_event")
    def test_invalid_signature_returns_400(self, mock_construct_event):
        mock_construct_event.side_effect = (
            stripe.error.SignatureVerificationError(
                "Invalid signature",
                "invalid_signature",
            )
        )

        response = self.client.post(
            self.url,
            data=b'{"id":"evt_invalid_signature","type":"test.event"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Invalid Stripe signature.",
        )

    @patch("apps.webhooks.views.StripeWebhookView.handle_event")
    @patch("apps.webhooks.views.stripe.Webhook.construct_event")
    def test_valid_event_is_processed(
        self,
        mock_construct_event,
        mock_handle_event,
    ):
        event = {
            "id": "evt_endpoint_valid_test",
            "type": "test.event",
            "data": {"object": {}},
        }

        mock_construct_event.return_value = event

        response = self.client.post(
            self.url,
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        self.assertEqual(response.status_code, 200)
        mock_handle_event.assert_called_once_with(event)

    @patch("apps.webhooks.views.StripeWebhookView.handle_event")
    @patch("apps.webhooks.views.stripe.Webhook.construct_event")
    def test_duplicate_processed_event_is_not_processed_again(
        self,
        mock_construct_event,
        mock_handle_event,
    ):
        event = {
            "id": "evt_endpoint_duplicate_test",
            "type": "test.event",
            "data": {"object": {}},
        }

        mock_construct_event.return_value = event

        first_response = self.client.post(
            self.url,
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        second_response = self.client.post(
            self.url,
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(mock_handle_event.call_count, 1)


# =============================================================================
# INVOICE WEBHOOKS — Stripe API 2025-03-31+ payload shape
# =============================================================================
#
# Regression tests: newer Stripe API versions removed the top-level
# ``invoice.subscription`` field. Before this fix the invoice handlers
# returned silently, so payment success/failure never reached the local
# subscription (no PAST_DUE, no grace period, no notifications).


def make_new_api_invoice(subscription_id, **extra):
    """Invoice payload in the current Stripe API shape."""
    invoice = {
        "id": "in_test_new_shape",
        "object": "invoice",
        "parent": {
            "type": "subscription_details",
            "subscription_details": {
                "subscription": subscription_id,
            },
        },
    }
    invoice.update(extra)
    return invoice


class InvoiceSubscriptionIdExtractionTests(TestCase):
    def test_reads_new_api_parent_field(self):
        invoice = make_new_api_invoice("sub_new_123")

        self.assertEqual(
            StripeWebhookView.get_invoice_subscription_id(invoice),
            "sub_new_123",
        )

    def test_reads_legacy_top_level_field(self):
        invoice = {"subscription": "sub_legacy_123"}

        self.assertEqual(
            StripeWebhookView.get_invoice_subscription_id(invoice),
            "sub_legacy_123",
        )

    def test_reads_expanded_subscription_object(self):
        invoice = make_new_api_invoice({"id": "sub_expanded_123"})

        self.assertEqual(
            StripeWebhookView.get_invoice_subscription_id(invoice),
            "sub_expanded_123",
        )

    def test_falls_back_to_line_items(self):
        invoice = {
            "parent": None,
            "lines": {
                "data": [
                    {"parent": {"subscription_item_details": {
                        "subscription": "sub_line_123",
                    }}},
                ]
            },
        }

        self.assertEqual(
            StripeWebhookView.get_invoice_subscription_id(invoice),
            "sub_line_123",
        )

    def test_one_off_invoice_returns_none(self):
        invoice = {"id": "in_one_off", "parent": None, "lines": {"data": []}}

        self.assertIsNone(
            StripeWebhookView.get_invoice_subscription_id(invoice)
        )


class InvoiceWebhookHandlerTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Invoice Webhook Org",
            slug="invoice-webhook-org",
        )

        self.pro_plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            stripe_monthly_price_id="price_pro_monthly_inv",
            stripe_annual_price_id="price_pro_annual_inv",
        )

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            stripe_subscription_id="sub_invoice_handler_test",
        )

        self.view = StripeWebhookView()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    def test_payment_failed_new_shape_marks_past_due(
        self,
        mock_notification,
    ):
        event = {
            "type": "invoice.payment_failed",
            "data": {
                "object": make_new_api_invoice(
                    "sub_invoice_handler_test",
                    attempt_count=2,
                )
            },
        }

        self.view.handle_invoice_payment_failed(event)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.PAST_DUE,
        )
        self.assertEqual(self.subscription.payment_retry_count, 2)
        self.assertIsNotNone(self.subscription.payment_failed_at)
        self.assertIsNotNone(self.subscription.grace_period_end)
        mock_notification.assert_called_once()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_payment_succeeded_new_shape_clears_dunning(
        self,
        mock_retrieve,
        mock_notification,
    ):
        from django.utils import timezone

        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.payment_failed_at = timezone.now()
        self.subscription.payment_retry_count = 3
        self.subscription.grace_period_end = timezone.now()
        self.subscription.save()

        start_timestamp = 1798932600
        end_timestamp = 1801611000

        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_invoice_handler_test",
            "status": "active",
            "items": {
                "data": [
                    {
                        "price": {"id": "price_pro_monthly_inv"},
                        "current_period_start": start_timestamp,
                        "current_period_end": end_timestamp,
                    }
                ]
            },
        }

        event = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": make_new_api_invoice(
                    "sub_invoice_handler_test"
                )
            },
        }

        self.view.handle_invoice_payment_succeeded(event)

        self.subscription.refresh_from_db()

        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )
        self.assertIsNone(self.subscription.payment_failed_at)
        self.assertEqual(self.subscription.payment_retry_count, 0)
        self.assertIsNone(self.subscription.grace_period_end)
        self.assertEqual(
            self.subscription.current_period_end,
            datetime.fromtimestamp(
                end_timestamp, tz=datetime_timezone.utc
            ),
        )
        mock_retrieve.assert_called_once_with("sub_invoice_handler_test")
        mock_notification.assert_called_once()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_invoice_for_unknown_subscription_is_ignored(
        self,
        mock_retrieve,
        mock_notification,
    ):
        event = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": make_new_api_invoice("sub_not_in_database")
            },
        }

        self.view.handle_invoice_payment_succeeded(event)

        mock_retrieve.assert_not_called()
        mock_notification.assert_not_called()

        self.subscription.refresh_from_db()
        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )


# =============================================================================
# CHECKOUT SESSION COMPLETED — Phase 2
# =============================================================================


class CheckoutCompletedHandlerTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Checkout Webhook Org",
            slug="checkout-webhook-org",
        )

        self.free_plan = Plan.objects.create(code="FREE", name="Free")

        self.enterprise_plan = Plan.objects.create(
            code="ENTERPRISE",
            name="Enterprise",
            stripe_monthly_price_id="price_ent_monthly_co",
            stripe_annual_price_id="price_ent_annual_co",
        )

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.free_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
        )

        self.view = StripeWebhookView()

    def make_event(self, metadata=None, client_reference_id=None,
                   subscription="sub_checkout_new"):
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_checkout",
                    "customer": "cus_checkout_new",
                    "subscription": subscription,
                    "client_reference_id": client_reference_id,
                    "metadata": metadata or {},
                }
            },
        }

    def stripe_subscription(self, price_id="price_ent_annual_co"):
        return {
            "id": "sub_checkout_new",
            "status": "active",
            "cancel_at_period_end": False,
            "canceled_at": None,
            "items": {
                "data": [
                    {
                        "price": {"id": price_id},
                        "current_period_start": 1798932600,
                        "current_period_end": 1830468600,
                    }
                ]
            },
        }

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_plan_comes_from_stripe_price_not_metadata(self, mock_retrieve):
        mock_retrieve.return_value.to_dict.return_value = (
            self.stripe_subscription("price_ent_annual_co")
        )

        # Metadata claims PRO MONTHLY, but Stripe says ENTERPRISE ANNUAL.
        event = self.make_event(metadata={
            "organization_id": str(self.organization.id),
            "plan_code": "PRO",
            "interval": "MONTHLY",
        })

        self.view.handle_checkout_completed(event)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.enterprise_plan)
        self.assertEqual(
            self.subscription.interval,
            Subscription.Interval.ANNUAL,
        )
        self.assertEqual(
            self.subscription.stripe_subscription_id,
            "sub_checkout_new",
        )
        self.assertEqual(
            self.subscription.stripe_customer_id,
            "cus_checkout_new",
        )

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_falls_back_to_client_reference_id(self, mock_retrieve):
        mock_retrieve.return_value.to_dict.return_value = (
            self.stripe_subscription()
        )

        event = self.make_event(
            metadata={},
            client_reference_id=str(self.organization.id),
        )

        self.view.handle_checkout_completed(event)

        self.subscription.refresh_from_db()
        self.assertEqual(
            self.subscription.stripe_subscription_id,
            "sub_checkout_new",
        )

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_missing_org_reference_raises_clear_error(self, mock_retrieve):
        event = self.make_event(metadata={}, client_reference_id=None)

        with self.assertRaisesMessage(ValueError, "stripe trigger"):
            self.view.handle_checkout_completed(event)

        mock_retrieve.assert_not_called()

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_refuses_to_overwrite_different_live_subscription(
        self,
        mock_retrieve,
    ):
        self.subscription.stripe_subscription_id = "sub_existing_live"
        self.subscription.stripe_customer_id = "cus_existing"
        self.subscription.save()

        event = self.make_event(metadata={
            "organization_id": str(self.organization.id),
        })

        with self.assertRaisesMessage(ValueError, "refusing to overwrite"):
            self.view.handle_checkout_completed(event)

        mock_retrieve.assert_not_called()

        self.subscription.refresh_from_db()
        self.assertEqual(
            self.subscription.stripe_subscription_id,
            "sub_existing_live",
        )

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_same_subscription_is_idempotent(self, mock_retrieve):
        self.subscription.stripe_subscription_id = "sub_checkout_new"
        self.subscription.save()

        mock_retrieve.return_value.to_dict.return_value = (
            self.stripe_subscription()
        )

        event = self.make_event(metadata={
            "organization_id": str(self.organization.id),
        })

        self.view.handle_checkout_completed(event)
        self.view.handle_checkout_completed(event)

        self.assertEqual(
            Subscription.objects.filter(
                organization=self.organization
            ).count(),
            1,
        )

    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_canceled_subscription_can_be_replaced(self, mock_retrieve):
        self.subscription.stripe_subscription_id = "sub_old_canceled"
        self.subscription.status = Subscription.Status.CANCELED
        self.subscription.save()

        mock_retrieve.return_value.to_dict.return_value = (
            self.stripe_subscription()
        )

        event = self.make_event(metadata={
            "organization_id": str(self.organization.id),
        })

        self.view.handle_checkout_completed(event)

        self.subscription.refresh_from_db()
        self.assertEqual(
            self.subscription.stripe_subscription_id,
            "sub_checkout_new",
        )
        self.assertEqual(
            self.subscription.status,
            Subscription.Status.ACTIVE,
        )


# =============================================================================
# PAYMENTS + STRIPE INVOICE MIRROR — Phase 5
# =============================================================================

from decimal import Decimal

from apps.invoices.models import Invoice, Payment


def make_paid_stripe_invoice(subscription_id, **extra):
    invoice = {
        "id": "in_test_paid_001",
        "object": "invoice",
        "number": "ABCD1234-0001",
        "currency": "usd",
        "customer_email": "payer@example.com",
        "created": 1798932600,
        "due_date": None,
        "total": 3190,
        "amount_paid": 3190,
        "total_taxes": [{"amount": 290}],
        "status_transitions": {"paid_at": 1798932700},
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": subscription_id},
        },
        "lines": {
            "data": [
                {
                    "description": "1 x Pro (at $29.00 / month)",
                    "amount": 2900,
                    "quantity": 1,
                }
            ]
        },
    }
    invoice.update(extra)
    return invoice


class StripeInvoiceMirrorTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Mirror Org",
            slug="mirror-org",
            billing_email="billing@mirror.example",
        )
        self.pro_plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            stripe_monthly_price_id="price_pro_monthly_mirror",
        )
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.pro_plan,
            status=Subscription.Status.ACTIVE,
            stripe_subscription_id="sub_mirror_test",
        )
        self.view = StripeWebhookView()

    def paid_event(self, event_type="invoice.paid", **extra):
        return {
            "type": event_type,
            "data": {
                "object": make_paid_stripe_invoice(
                    "sub_mirror_test", **extra
                )
            },
        }

    def test_invoice_paid_creates_local_invoice_and_payment(self):
        self.view.handle_event(self.paid_event())

        invoice = Invoice.objects.get(stripe_invoice_id="in_test_paid_001")
        self.assertEqual(invoice.organization, self.organization)
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.invoice_number, "ABCD1234-0001")
        self.assertEqual(invoice.total, Decimal("31.90"))
        self.assertEqual(invoice.tax, Decimal("2.90"))
        self.assertEqual(invoice.subtotal, Decimal("29.00"))
        self.assertEqual(invoice.currency, "USD")
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.first().amount, Decimal("29.00"))

        payment = Payment.objects.get(stripe_invoice_id="in_test_paid_001")
        self.assertEqual(payment.amount, Decimal("31.90"))
        self.assertEqual(payment.method, Payment.Method.STRIPE)
        self.assertEqual(payment.invoice, invoice)

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_both_stripe_events_record_money_once(
        self,
        mock_retrieve,
        mock_notification,
    ):
        mock_retrieve.return_value.to_dict.return_value = {
            "id": "sub_mirror_test",
            "status": "active",
            "items": {"data": [{
                "price": {"id": "price_pro_monthly_mirror"},
                "current_period_start": 1798932600,
                "current_period_end": 1801611000,
            }]},
        }

        # Stripe sends both events for one payment, and may retry each.
        self.view.handle_event(self.paid_event("invoice.payment_succeeded"))
        self.view.handle_event(self.paid_event("invoice.paid"))
        self.view.handle_event(self.paid_event("invoice.paid"))

        self.assertEqual(
            Invoice.objects.filter(
                stripe_invoice_id="in_test_paid_001"
            ).count(),
            1,
        )
        self.assertEqual(Payment.objects.count(), 1)
        mock_notification.assert_called_once()

    def test_zero_amount_invoice_creates_no_payment(self):
        self.view.handle_event(
            self.paid_event(total=0, amount_paid=0, total_taxes=[])
        )

        self.assertTrue(
            Invoice.objects.filter(
                stripe_invoice_id="in_test_paid_001"
            ).exists()
        )
        self.assertEqual(Payment.objects.count(), 0)

    def test_org_found_from_subscription_metadata(self):
        self.subscription.stripe_subscription_id = None
        self.subscription.save()

        event = self.paid_event()
        event["data"]["object"]["parent"]["subscription_details"][
            "metadata"
        ] = {"organization_id": str(self.organization.id)}

        self.view.handle_event(event)

        self.assertEqual(
            Payment.objects.get().organization,
            self.organization,
        )

    def test_unknown_organization_is_ignored(self):
        event = self.paid_event()
        event["data"]["object"]["parent"]["subscription_details"][
            "subscription"
        ] = "sub_unknown"

        self.view.handle_event(event)

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)


class InvoiceCheckoutPaymentTests(TestCase):
    def setUp(self):
        from datetime import date

        self.organization = Organization.objects.create(
            name="Checkout Pay Org",
            slug="checkout-pay-org",
        )
        self.invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number="INV-000009",
            status=Invoice.Status.OPEN,
            issue_date=date(2026, 11, 1),
            total=Decimal("120.00"),
            subtotal=Decimal("120.00"),
            billing_email="client@example.com",
        )
        self.view = StripeWebhookView()

    def session_event(self):
        return {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_invoice_pay",
                "payment_status": "paid",
                "payment_intent": "pi_test_123",
                "amount_total": 12000,
                "currency": "usd",
                "metadata": {
                    "payment_type": "invoice",
                    "invoice_id": str(self.invoice.id),
                    "organization_id": str(self.organization.id),
                },
            }},
        }

    def test_invoice_checkout_records_payment_once(self):
        self.view.handle_event(self.session_event())
        self.view.handle_event(self.session_event())

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal("120.00"))
        self.assertEqual(payment.stripe_payment_intent_id, "pi_test_123")
        self.assertEqual(payment.invoice, self.invoice)

    def test_invoice_checkout_is_logged_once_in_activity(self):
        from apps.audit.models import AuditLog

        self.view.handle_event(self.session_event())
        self.view.handle_event(self.session_event())

        log = AuditLog.objects.get(action="INVOICE_PAID")
        self.assertEqual(log.organization, self.organization)
        self.assertIsNone(log.user)
        self.assertIn("INV-000009", log.description)
        self.assertIn("client@example.com", log.description)
        self.assertIn("USD 120.00", log.description)


class RejectedUpgradeChargeTests(TestCase):
    """
    A declined up-front upgrade charge must not start dunning: the
    subscription is still active on its old plan.
    """

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Upgrade Org", slug="upgrade-org",
        )
        plan = Plan.objects.create(
            code="PRO",
            name="Pro",
            stripe_monthly_price_id="price_pro_monthly_upg",
            stripe_annual_price_id="price_pro_annual_upg",
        )
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            stripe_subscription_id="sub_upgrade_test",
        )
        self.view = StripeWebhookView()

    def fail_invoice(self, **invoice_fields):
        self.view.handle_invoice_payment_failed({
            "type": "invoice.payment_failed",
            "data": {"object": make_new_api_invoice(
                "sub_upgrade_test", **invoice_fields
            )},
        })
        self.subscription.refresh_from_db()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_declined_upgrade_keeps_subscription_active(
        self, mock_retrieve, mock_notification,
    ):
        mock_retrieve.return_value.to_dict.return_value = {
            "status": "active",
        }

        self.fail_invoice(billing_reason="subscription_update")

        self.assertEqual(
            self.subscription.status, Subscription.Status.ACTIVE,
        )
        self.assertIsNone(self.subscription.grace_period_end)
        mock_notification.assert_not_called()

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_update_charge_on_past_due_subscription_starts_dunning(
        self, mock_retrieve, mock_notification,
    ):
        mock_retrieve.return_value.to_dict.return_value = {
            "status": "past_due",
        }

        self.fail_invoice(billing_reason="subscription_update")

        self.assertEqual(
            self.subscription.status, Subscription.Status.PAST_DUE,
        )
        self.assertIsNotNone(self.subscription.grace_period_end)

    @patch(
        "apps.webhooks.views.create_notification_for_organization_members"
    )
    @patch("apps.webhooks.views.stripe.Subscription.retrieve")
    def test_failed_renewal_starts_dunning_without_lookup(
        self, mock_retrieve, mock_notification,
    ):
        self.fail_invoice(billing_reason="subscription_cycle")

        self.assertEqual(
            self.subscription.status, Subscription.Status.PAST_DUE,
        )
        mock_retrieve.assert_not_called()
