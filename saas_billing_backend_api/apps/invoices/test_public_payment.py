from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.core import mail, signing
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Invoice
from .public import TOKEN_SALT, make_payment_token, payment_link
from .services import send_invoice_email
from .tests import InvoiceTestBase


@override_settings(FRONTEND_URL="https://app.example.com")
class PublicInvoicePaymentTests(APITestCase):
    """Customer pays from the link in the invoice email, without logging in."""

    setUp = InvoiceTestBase.setUp

    def open_invoice(self, invoice=None):
        invoice = invoice or self.invoice
        invoice.status = Invoice.Status.OPEN
        invoice.save()
        return invoice

    def view_url(self, token):
        return reverse("public-invoice", kwargs={"token": token})

    def pay_url(self, token):
        return reverse("public-invoice-pay", kwargs={"token": token})

    def test_invoice_email_contains_payment_link(self):
        mail.outbox = []
        send_invoice_email(self.open_invoice(), b"%PDF-TEST")

        body = mail.outbox[0].body
        self.assertIn("https://app.example.com/pay/", body)
        self.assertIn(payment_link(self.invoice), body)

    def test_customer_sees_invoice_without_login(self):
        token = make_payment_token(self.open_invoice())

        response = self.client.get(self.view_url(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_number"], "INV-000001")
        self.assertEqual(response.data["organization_name"], "Acme Corporation")
        self.assertEqual(response.data["total"], "110.00")
        self.assertTrue(response.data["payable"])
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            response.data["items"][0]["description"],
            "Monthly Subscription",
        )

    def test_tampered_or_foreign_token_is_rejected(self):
        token = make_payment_token(self.open_invoice())

        self.assertEqual(
            self.client.get(self.view_url(token + "x")).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Signed with another salt (e.g. some other feature's token).
        forged = signing.dumps(str(self.invoice.id), salt="other")
        self.assertEqual(
            self.client.get(self.view_url(forged)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_draft_and_paid_invoices_are_not_payable(self):
        token = make_payment_token(self.invoice)  # still DRAFT

        response = self.client.get(self.view_url(token))
        self.assertFalse(response.data["payable"])

        response = self.client.post(self.pay_url(token))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.invoice.status = Invoice.Status.PAID
        self.invoice.save()

        response = self.client.post(self.pay_url(token))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been paid", response.data["detail"])

    @patch("apps.invoices.views.stripe.checkout.Session.create")
    def test_customer_starts_checkout(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="cs_test_public",
            url="https://checkout.stripe.com/pay/cs_test_public",
        )
        token = make_payment_token(self.open_invoice())

        response = self.client.post(self.pay_url(token))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.stripe.com/pay/cs_test_public",
        )

        kwargs = mock_create.call_args.kwargs
        page = f"https://app.example.com/pay/{token}"
        self.assertEqual(kwargs["success_url"], f"{page}?paid=1")
        self.assertEqual(kwargs["cancel_url"], page)
        self.assertEqual(kwargs["metadata"]["payment_type"], "invoice")
        self.assertEqual(kwargs["metadata"]["invoice_id"], str(self.invoice.id))
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 11000)

    @patch("apps.invoices.views.stripe.checkout.Session.create")
    def test_eur_invoice_is_charged_in_eur(self, mock_create):
        mock_create.return_value = SimpleNamespace(id="cs", url="https://x")
        self.invoice.currency = Invoice.Currency.EUR
        token = make_payment_token(self.open_invoice())

        response = self.client.post(self.pay_url(token))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        price = mock_create.call_args.kwargs["line_items"][0]["price_data"]
        self.assertEqual(price["currency"], "eur")

    @patch("apps.invoices.views.stripe.checkout.Session.create")
    def test_stripe_failure_returns_502(self, mock_create):
        mock_create.side_effect = stripe.error.StripeError("down")
        token = make_payment_token(self.open_invoice())

        response = self.client.post(self.pay_url(token))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_inactive_organization_link_stops_working(self):
        token = make_payment_token(self.open_invoice())
        self.organization.is_active = False
        self.organization.save()

        self.assertEqual(
            self.client.get(self.view_url(token)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_token_uses_its_own_salt(self):
        token = make_payment_token(self.invoice)
        self.assertEqual(
            signing.loads(token, salt=TOKEN_SALT),
            {"i": str(self.invoice.id), "v": self.invoice.payment_link_version},
        )
