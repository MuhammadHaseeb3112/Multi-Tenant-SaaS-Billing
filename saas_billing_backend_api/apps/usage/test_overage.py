"""
Phase 8: usage overage — enforcement, period-end billing via the
``invoice.created`` webhook, manual billing command, API.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import stripe
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import Subscription
from apps.webhooks.models import WebhookEvent

from .models import ApiKey, OverageCharge, UsageRecord
from .services import calculate_overage_amount
from .tests import UsageTestBase


STRIPE_ITEM = "apps.usage.overage.stripe.InvoiceItem.create"


class OverageTestBase(UsageTestBase):

    def setUp(self):
        super().setUp()
        # PRO: 10,000 included, $2.00 per extra 1,000.
        self.pro_plan.overage_price_per_1000 = Decimal("2.00")
        self.pro_plan.save()

        self.api_key, self.raw_key = ApiKey.create_key(
            organization=self.organization, name="Server"
        )

    def fill_to_limit(self, extra=0):
        UsageRecord.objects.create(
            organization=self.organization,
            quantity=self.pro_plan.api_request_limit + extra,
        )

    def call_api(self):
        return self.client.post(
            reverse("product-text-analyze"),
            {"text": "overage test"},
            format="json",
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )


# =============================================================================
# Enforcement
# =============================================================================


class OverageEnforcementTests(OverageTestBase):

    def test_paid_plan_with_overage_allows_requests_over_limit(self):
        self.fill_to_limit()

        response = self.call_api()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-RateLimit-Remaining"], "0")
        self.assertEqual(response["X-Overage-Requests"], "1")

        self.authenticate(self.member)
        summary = self.client.get(self.summary_url()).data
        self.assertTrue(summary["overage_enabled"])
        self.assertEqual(summary["overage_requests"], 1)
        self.assertEqual(summary["estimated_overage_amount"], "0.01")

    def test_overage_cap_is_enforced(self):
        self.pro_plan.max_overage_requests = 2
        self.pro_plan.save()
        self.fill_to_limit()

        self.assertEqual(self.call_api().status_code, status.HTTP_200_OK)
        self.assertEqual(self.call_api().status_code, status.HTTP_200_OK)

        response = self.call_api()
        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertIn("cap", response.data["detail"])
        self.assertEqual(response.data["overage_requests"], 2)

    def test_plan_without_overage_price_keeps_hard_limit(self):
        self.pro_plan.overage_price_per_1000 = Decimal("0.00")
        self.pro_plan.save()
        self.fill_to_limit()

        response = self.call_api()

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertNotIn("X-Overage-Requests", response)

    def test_past_due_subscription_gets_no_overage(self):
        self.subscription.status = Subscription.Status.PAST_DUE
        self.subscription.save()
        self.fill_to_limit()

        self.assertEqual(
            self.call_api().status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_subscription_without_stripe_billing_gets_no_overage(self):
        # Nothing to put the overage on -> it must stay a hard limit.
        self.subscription.stripe_subscription_id = None
        self.subscription.save()
        self.fill_to_limit()

        self.assertEqual(
            self.call_api().status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_manual_record_can_also_go_into_overage(self):
        self.fill_to_limit()
        self.authenticate(self.owner)

        response = self.client.post(
            self.record_url(), {"quantity": 5}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class OverageAmountTests(APITestCase):

    def test_amount_rounds_up_to_the_cent(self):
        self.assertEqual(
            calculate_overage_amount(1, Decimal("1.00")), Decimal("0.01")
        )
        self.assertEqual(
            calculate_overage_amount(1500, Decimal("2.00")),
            Decimal("3.00"),
        )
        self.assertEqual(
            calculate_overage_amount(1001, Decimal("2.00")),
            Decimal("2.01"),
        )
        self.assertEqual(
            calculate_overage_amount(0, Decimal("2.00")), Decimal("0.00")
        )
        self.assertEqual(
            calculate_overage_amount(500, Decimal("0.00")),
            Decimal("0.00"),
        )


# =============================================================================
# Period-end billing via invoice.created
# =============================================================================


class OverageBillingWebhookTests(OverageTestBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("stripe-webhook")

        # The period that just closed.
        self.closed_start = datetime(2026, 10, 1, tzinfo=dt_timezone.utc)
        self.closed_end = datetime(2026, 11, 1, tzinfo=dt_timezone.utc)

    def usage_at(self, when, quantity):
        record = UsageRecord.objects.create(
            organization=self.organization, quantity=quantity
        )
        UsageRecord.objects.filter(pk=record.pk).update(recorded_at=when)

    def invoice_event(self, event_id="evt_inv_created", **invoice_extra):
        invoice = {
            "id": "in_renewal_1",
            "object": "invoice",
            "status": "draft",
            "billing_reason": "subscription_cycle",
            "currency": "usd",
            "customer": "cus_test_usage",
            "period_start": int(self.closed_start.timestamp()),
            "period_end": int(self.closed_end.timestamp()),
            "parent": {
                "type": "subscription_details",
                "subscription_details": {
                    "subscription": "sub_test_usage",
                },
            },
        }
        invoice.update(invoice_extra)
        return {
            "id": event_id,
            "type": "invoice.created",
            "data": {"object": invoice},
        }

    def post(self, event):
        with patch(
            "apps.webhooks.views.stripe.Webhook.construct_event",
            return_value=event,
        ):
            return self.client.post(
                self.url,
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig",
            )

    @patch(STRIPE_ITEM, return_value={"id": "ii_overage_1"})
    def test_renewal_invoice_gets_overage_item(self, mock_create):
        # 10,000 included; 11,500 used in the closed period.
        self.usage_at(self.closed_start + timedelta(days=3), 6000)
        self.usage_at(self.closed_end - timedelta(hours=1), 5500)
        # Outside the closed period -> not billed now.
        self.usage_at(self.closed_start - timedelta(days=1), 9000)
        self.usage_at(self.closed_end + timedelta(hours=1), 9000)

        response = self.post(self.invoice_event())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["invoice"], "in_renewal_1")
        self.assertEqual(kwargs["customer"], "cus_test_usage")
        self.assertEqual(kwargs["amount"], 300)  # 1,500 x $2/1000 = $3
        self.assertEqual(kwargs["currency"], "usd")
        self.assertEqual(
            kwargs["idempotency_key"],
            f"overage-{self.subscription.id}-"
            f"{int(self.closed_start.timestamp())}",
        )
        self.assertNotIn("subscription", kwargs)

        charge = OverageCharge.objects.get()
        self.assertEqual(charge.overage_requests, 1500)
        self.assertEqual(charge.used_requests, 11500)
        self.assertEqual(charge.amount, Decimal("3.00"))
        self.assertEqual(charge.status, OverageCharge.Status.BILLED)
        self.assertEqual(charge.stripe_invoice_id, "in_renewal_1")
        self.assertEqual(charge.period_start, self.closed_start)

    @patch(STRIPE_ITEM, return_value={"id": "ii_overage_1"})
    def test_same_period_is_never_billed_twice(self, mock_create):
        self.usage_at(self.closed_start + timedelta(days=1), 12000)

        self.post(self.invoice_event("evt_a"))
        # A different event for the same period (e.g. duplicate delivery
        # under another id) must not bill again.
        self.post(self.invoice_event("evt_b"))

        self.assertEqual(mock_create.call_count, 1)
        self.assertEqual(OverageCharge.objects.count(), 1)

    @patch(STRIPE_ITEM)
    def test_no_overage_means_no_invoice_item(self, mock_create):
        self.usage_at(self.closed_start + timedelta(days=1), 9999)

        response = self.post(self.invoice_event())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_create.assert_not_called()
        self.assertFalse(OverageCharge.objects.exists())

    @patch(STRIPE_ITEM)
    def test_first_invoice_and_finalized_invoices_are_ignored(
        self, mock_create
    ):
        self.usage_at(self.closed_start + timedelta(days=1), 20000)

        self.post(self.invoice_event(
            "evt_create", billing_reason="subscription_create"
        ))
        self.post(self.invoice_event("evt_open", status="open"))

        mock_create.assert_not_called()

    @patch(STRIPE_ITEM)
    def test_plan_without_overage_price_bills_nothing(self, mock_create):
        self.pro_plan.overage_price_per_1000 = Decimal("0.00")
        self.pro_plan.save()
        self.usage_at(self.closed_start + timedelta(days=1), 20000)

        self.post(self.invoice_event())

        mock_create.assert_not_called()

    def test_stripe_error_leaves_event_unprocessed_and_retry_bills(self):
        self.usage_at(self.closed_start + timedelta(days=1), 11000)
        event = self.invoice_event("evt_retry")

        with patch(
            STRIPE_ITEM,
            side_effect=stripe.error.APIConnectionError("down"),
        ):
            with self.assertRaises(stripe.error.APIConnectionError):
                self.post(event)

        self.assertFalse(OverageCharge.objects.exists())
        self.assertFalse(
            WebhookEvent.objects.get(stripe_event_id="evt_retry").processed
        )

        with patch(STRIPE_ITEM, return_value={"id": "ii_retry"}):
            response = self.post(event)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(OverageCharge.objects.get().amount, Decimal("2.00"))

    @patch(STRIPE_ITEM)
    def test_unknown_subscription_is_ignored(self, mock_create):
        event = self.invoice_event()
        event["data"]["object"]["parent"]["subscription_details"][
            "subscription"
        ] = "sub_unknown"

        response = self.post(event)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_create.assert_not_called()


# =============================================================================
# Manual billing command
# =============================================================================


class BillOverageCommandTests(OverageTestBase):

    def setUp(self):
        super().setUp()
        self.start = "2026-09-01T00:00:00Z"
        self.end = "2026-10-01T00:00:00Z"
        record = UsageRecord.objects.create(
            organization=self.organization, quantity=10250
        )
        UsageRecord.objects.filter(pk=record.pk).update(
            recorded_at=datetime(2026, 9, 15, tzinfo=dt_timezone.utc)
        )

    def run_cmd(self, *extra):
        out = StringIO()
        call_command(
            "bill_overage",
            "--organization", str(self.organization.id),
            "--start", self.start,
            "--end", self.end,
            *extra,
            stdout=out,
        )
        return out.getvalue()

    @patch(STRIPE_ITEM)
    def test_dry_run_bills_nothing(self, mock_create):
        output = self.run_cmd("--dry-run")

        self.assertIn("overage 250", output)
        self.assertIn("0.50", output)
        mock_create.assert_not_called()

    @patch(STRIPE_ITEM, return_value={"id": "ii_manual"})
    def test_creates_pending_item_once(self, mock_create):
        self.run_cmd()
        output = self.run_cmd()

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["subscription"], "sub_test_usage")
        self.assertNotIn("invoice", kwargs)
        self.assertEqual(kwargs["amount"], 50)
        charge = OverageCharge.objects.get()
        self.assertEqual(
            charge.status, OverageCharge.Status.PENDING_NEXT_INVOICE
        )
        self.assertIn("Already billed", output)


# =============================================================================
# API
# =============================================================================


class OverageChargeAPITests(OverageTestBase):

    def setUp(self):
        super().setUp()
        OverageCharge.objects.create(
            organization=self.organization,
            subscription=self.subscription,
            period_start=timezone.now() - timedelta(days=40),
            period_end=timezone.now() - timedelta(days=10),
            included_requests=10000,
            used_requests=10500,
            overage_requests=500,
            price_per_1000=Decimal("2.00"),
            amount=Decimal("1.00"),
            status=OverageCharge.Status.BILLED,
            stripe_invoice_id="in_x",
            stripe_invoice_item_id="ii_x",
        )
        self.url = reverse(
            "overage-charge-list",
            kwargs={"organization_id": self.organization.id},
        )

    def test_member_can_list_overage_charges(self):
        self.authenticate(self.member)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["amount"], "1.00")
        self.assertNotIn("stripe_invoice_item_id", response.data[0])

    def test_other_tenant_cannot_list(self):
        self.authenticate(self.other_owner)

        self.assertEqual(
            self.client.get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_plans_endpoint_shows_overage_pricing(self):
        self.authenticate(self.owner)

        response = self.client.get(reverse("billing-plans"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plans = response.data
        if isinstance(plans, dict):
            plans = plans.get("results", plans)
        pro = next(p for p in plans if p["code"] == "PRO")
        self.assertEqual(pro["overage_price_per_1000"], "2.00")
