"""
Refunds, credit notes and net revenue; plus the row lock that stops two
simultaneous deliveries of one Stripe event from both being processed.
"""

import json
import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import stripe

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.billing.models import Plan, Subscription
from apps.tenants.models import Membership, Organization
from apps.webhooks.models import WebhookEvent

from .models import CreditNote, Invoice, Payment, Refund
from .refunds import sync_stripe_refund


WEBHOOK_SIG = "apps.webhooks.views.stripe.Webhook.construct_event"
INVOICE_PAYMENT_LIST = "apps.invoices.refunds.stripe.InvoicePayment.list"
REFUND_LIST = "apps.invoices.refunds.stripe.Refund.list"


def stripe_refund(refund_id="re_1", amount=1000, status="succeeded",
                  payment_intent="pi_1", **extra):
    data = {
        "id": refund_id,
        "object": "refund",
        "amount": amount,
        "currency": "usd",
        "status": status,
        "payment_intent": payment_intent,
        "charge": "ch_1",
        "reason": "requested_by_customer",
        "created": int(timezone.now().timestamp()),
    }
    data.update(extra)
    return data


def as_stripe(cls, data):
    """
    What the Stripe library really returns from an API call: an API
    object, not a dict (stripe-python 15 raises on .get()). Mocks must
    return these, or code that forgets .to_dict() passes the tests and
    fails against Stripe.
    """

    return cls.construct_from(data, "sk_test_mock")


class RefundTestBase(TestCase):

    def setUp(self):
        self.plan = Plan.objects.create(
            code="PRO", name="Pro", monthly_price=Decimal("29.00")
        )
        self.organization = Organization.objects.create(
            name="Acme", slug="acme", billing_email="b@acme.com"
        )
        self.owner = User.objects.create_user(
            email="owner@acme.com", password="TestPassword123"
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            stripe_customer_id="cus_acme",
            stripe_subscription_id="sub_acme",
        )
        self.invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number="INV-1",
            status=Invoice.Status.PAID,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            currency="USD",
            subtotal=Decimal("29.00"),
            tax=Decimal("0.00"),
            total=Decimal("29.00"),
            stripe_invoice_id="in_sub_1",
        )
        # Subscription invoice payment: Stripe API 2025+ gives no
        # payment_intent on the invoice, so it is not stored.
        self.payment = Payment.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            amount=Decimal("29.00"),
            currency="USD",
            method=Payment.Method.STRIPE,
            stripe_invoice_id="in_sub_1",
            paid_at=timezone.now() - timedelta(days=2),
        )

    def invoice_payment_lookup(self, invoice_id="in_sub_1"):
        return as_stripe(
            stripe.ListObject,
            {
                "object": "list",
                "data": [
                    {"object": "invoice_payment", "invoice": invoice_id}
                ],
            },
        )


class RefundSyncTests(RefundTestBase):

    def test_partial_refund_found_via_invoice_payment_lookup(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ) as lookup:
            refund = sync_stripe_refund(stripe_refund(amount=1000))

        lookup.assert_called_once_with(
            payment={"type": "payment_intent", "payment_intent": "pi_1"},
            limit=1,
        )
        self.payment.refresh_from_db()
        self.assertEqual(refund.payment, self.payment)
        self.assertEqual(refund.organization, self.organization)
        self.assertEqual(self.payment.amount_refunded, Decimal("10.00"))
        self.assertEqual(
            self.payment.status, Payment.Status.PARTIALLY_REFUNDED
        )
        # The PaymentIntent is remembered: next refund needs no lookup.
        self.assertEqual(self.payment.stripe_payment_intent_id, "pi_1")

    def test_second_refund_completes_it_without_another_lookup(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ) as lookup:
            sync_stripe_refund(stripe_refund("re_1", amount=1000))
            sync_stripe_refund(stripe_refund("re_2", amount=1900))

        self.assertEqual(lookup.call_count, 1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("29.00"))
        self.assertEqual(self.payment.status, Payment.Status.REFUNDED)

    def test_replayed_refund_is_counted_once(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(amount=500))
            sync_stripe_refund(stripe_refund(amount=500))

        self.assertEqual(Refund.objects.count(), 1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("5.00"))

    def test_pending_refund_does_not_reduce_until_succeeded(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(status="pending"))
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.amount_refunded, Decimal("0.00"))
            self.assertEqual(self.payment.status, Payment.Status.SUCCEEDED)

            sync_stripe_refund(stripe_refund(status="succeeded"))

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("10.00"))

    def test_failed_refund_gives_money_back_to_collected(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(status="succeeded"))
            sync_stripe_refund(stripe_refund(status="failed"))

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("0.00"))
        self.assertEqual(self.payment.status, Payment.Status.SUCCEEDED)

    def test_checkout_payment_matched_by_stored_payment_intent(self):
        self.payment.stripe_payment_intent_id = "pi_checkout"
        self.payment.save()

        with patch(INVOICE_PAYMENT_LIST) as lookup:
            sync_stripe_refund(stripe_refund(payment_intent="pi_checkout"))

        lookup.assert_not_called()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("10.00"))

    def test_unknown_payment_is_stored_without_payment(self):
        with patch(
            INVOICE_PAYMENT_LIST,
            return_value=as_stripe(
                stripe.ListObject, {"object": "list", "data": []}
            ),
        ):
            refund = sync_stripe_refund(
                stripe_refund(payment_intent="pi_unknown")
            )

        self.assertIsNone(refund.payment)
        self.assertIsNone(refund.organization)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("0.00"))

    def test_refund_larger_than_payment_is_capped(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(amount=999999))

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("29.00"))
        self.assertEqual(self.payment.status, Payment.Status.REFUNDED)


class RefundWebhookTests(RefundTestBase):

    def post_event(self, event):
        with patch(WEBHOOK_SIG, return_value=event):
            return APIClient().post(
                reverse("stripe-webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig",
            )

    def test_refund_created_event(self):
        event = {
            "id": "evt_refund_1",
            "type": "refund.created",
            "data": {"object": stripe_refund(amount=2900)},
        }

        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.REFUNDED)
        self.assertTrue(
            WebhookEvent.objects.get(stripe_event_id="evt_refund_1").processed
        )

    def test_charge_refunded_event_lists_refunds_from_stripe(self):
        refunds = MagicMock()
        refunds.auto_paging_iter.return_value = [
            as_stripe(stripe.Refund, stripe_refund("re_a", amount=400)),
            as_stripe(stripe.Refund, stripe_refund("re_b", amount=600)),
        ]
        event = {
            "id": "evt_charge_refunded",
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_1", "object": "charge"}},
        }

        with patch(REFUND_LIST, return_value=refunds) as refund_list, patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            response = self.post_event(event)

        self.assertEqual(response.status_code, 200)
        refund_list.assert_called_once_with(charge="ch_1", limit=100)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount_refunded, Decimal("10.00"))

    def test_credit_note_is_mirrored_and_voided(self):
        credit_note = {
            "id": "cn_1",
            "object": "credit_note",
            "customer": "cus_acme",
            "invoice": "in_sub_1",
            "number": "CN-0001",
            "total": 1500,
            "currency": "usd",
            "reason": "product_unsatisfactory",
            "status": "issued",
            "created": int(timezone.now().timestamp()),
        }

        self.post_event({
            "id": "evt_cn_1",
            "type": "credit_note.created",
            "data": {"object": credit_note},
        })

        note = CreditNote.objects.get()
        self.assertEqual(note.organization, self.organization)
        self.assertEqual(note.invoice, self.invoice)
        self.assertEqual(note.amount, Decimal("15.00"))
        self.assertEqual(note.status, CreditNote.Status.ISSUED)

        self.post_event({
            "id": "evt_cn_2",
            "type": "credit_note.voided",
            "data": {"object": dict(credit_note, status="void")},
        })

        self.assertEqual(CreditNote.objects.count(), 1)
        self.assertEqual(
            CreditNote.objects.get().status, CreditNote.Status.VOID
        )

    def test_credit_note_for_unknown_customer_is_ignored(self):
        response = self.post_event({
            "id": "evt_cn_x",
            "type": "credit_note.created",
            "data": {"object": {"id": "cn_x", "customer": "cus_other"}},
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CreditNote.objects.exists())


class NetRevenueTests(RefundTestBase):

    def test_org_total_paid_and_trend_are_net_of_refunds(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(amount=900))

        client = APIClient()
        client.force_authenticate(user=self.owner)

        data = client.get(
            reverse(
                "analytics-overview",
                kwargs={"organization_id": self.organization.id},
            )
        ).data

        # This payment is a platform subscription fee, so it is net
        # of refunds under "paid to platform" and stays out of the
        # customer revenue trend.
        self.assertEqual(data["total_paid"], "20.00")
        self.assertEqual(data["paid_to_platform"], "20.00")
        self.assertEqual(data["collected_from_customers"], "0.00")
        self.assertEqual(data["revenue_trend"], [])

    def test_fully_refunded_payment_counts_zero(self):
        with patch(
            INVOICE_PAYMENT_LIST, return_value=self.invoice_payment_lookup()
        ):
            sync_stripe_refund(stripe_refund(amount=2900))

        client = APIClient()
        client.force_authenticate(user=self.owner)

        data = client.get(
            reverse(
                "analytics-overview",
                kwargs={"organization_id": self.organization.id},
            )
        ).data

        self.assertEqual(data["total_paid"], "0.00")


class WebhookConcurrencyTests(TransactionTestCase):
    """
    Two deliveries of the SAME event at the same time: before the row
    lock both could pass the "already processed?" check and run the
    handler twice.
    """

    def test_simultaneous_duplicate_deliveries_process_once(self):
        event = {
            "id": "evt_concurrent",
            "type": "test.event",
            "data": {"object": {}},
        }
        calls = []
        start = threading.Barrier(2)

        def slow_handler(view, received_event):
            calls.append(received_event["id"])
            time.sleep(0.5)

        def deliver(results):
            try:
                start.wait()
                response = APIClient().post(
                    reverse("stripe-webhook"),
                    data=json.dumps(event),
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE="sig",
                )
                results.append(response.status_code)
            finally:
                connection.close()

        results = []

        with patch(WEBHOOK_SIG, return_value=event), patch(
            "apps.webhooks.views.StripeWebhookView.handle_event",
            slow_handler,
        ):
            # Create the stored event first so both threads race on the
            # processing step, not on the insert.
            WebhookEvent.objects.create(
                stripe_event_id="evt_concurrent",
                event_type="test.event",
                payload=event,
            )
            threads = [
                threading.Thread(target=deliver, args=(results,))
                for _ in range(2)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)

        self.assertEqual(sorted(results), [200, 200])
        self.assertEqual(calls, ["evt_concurrent"])
        self.assertTrue(
            WebhookEvent.objects.get(stripe_event_id="evt_concurrent").processed
        )
