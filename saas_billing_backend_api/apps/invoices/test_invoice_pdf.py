"""
Tests for the invoice PDF: who sells / who is billed, the status
badge and the paid / refunded / amount-due figures.
"""

from datetime import timedelta
from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import timezone

from apps.tenants.models import Organization

from .models import Invoice, InvoiceItem, Payment
from .services import build_invoice_pdf_context, generate_invoice_pdf


class InvoicePdfTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Acme Studio",
            slug="acme-studio",
            billing_email="billing@acme.test",
        )

    def make_invoice(self, **fields):
        defaults = {
            "organization": self.organization,
            "invoice_number": "INV-000001",
            "status": Invoice.Status.OPEN,
            "issue_date": timezone.localdate(),
            "due_date": timezone.localdate() + timedelta(days=7),
            "currency": "USD",
            "subtotal": Decimal("100.00"),
            "tax": Decimal("10.00"),
            "total": Decimal("110.00"),
            "billing_email": "customer@example.com",
        }
        defaults.update(fields)

        invoice = Invoice.objects.create(**defaults)

        InvoiceItem.objects.create(
            invoice=invoice,
            description="Design work",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            amount=Decimal("100.00"),
        )

        return invoice

    def pay(self, invoice, amount, refunded="0.00", status=None):
        return Payment.objects.create(
            organization=self.organization,
            invoice=invoice,
            amount=Decimal(amount),
            currency="USD",
            method=Payment.Method.MANUAL,
            status=status or Payment.Status.SUCCEEDED,
            amount_refunded=Decimal(refunded),
            paid_at=timezone.now(),
        )

    def render(self, invoice):
        return render_to_string(
            "invoices/invoice_pdf.html",
            build_invoice_pdf_context(invoice),
        )

    def test_customer_invoice_is_from_workspace_to_customer(self):
        context = build_invoice_pdf_context(self.make_invoice())

        self.assertEqual(context["seller_name"], "Acme Studio")
        self.assertEqual(context["seller_email"], "billing@acme.test")
        self.assertEqual(context["buyer_name"], "")
        self.assertEqual(context["buyer_email"], "customer@example.com")

    def test_platform_invoice_is_from_platform_to_workspace(self):
        context = build_invoice_pdf_context(self.make_invoice(
            stripe_invoice_id="in_test_123",
            due_date=None,
        ))

        self.assertEqual(context["seller_name"], "SaaS Billing")
        self.assertEqual(context["buyer_name"], "Acme Studio")

    def test_open_invoice_shows_amount_due(self):
        context = build_invoice_pdf_context(self.make_invoice())

        self.assertEqual(context["badge"], "OPEN")
        self.assertEqual(context["amount_due"], Decimal("110.00"))
        self.assertIsNone(context["paid_at"])

    def test_open_invoice_past_due_date_is_overdue(self):
        context = build_invoice_pdf_context(self.make_invoice(
            due_date=timezone.localdate() - timedelta(days=1),
        ))

        self.assertEqual(context["badge"], "OVERDUE")
        self.assertEqual(context["badge_class"], "badge-red")

    def test_paid_invoice_shows_payment_and_nothing_due(self):
        invoice = self.make_invoice(status=Invoice.Status.PAID)
        self.pay(invoice, "110.00")

        context = build_invoice_pdf_context(invoice)

        self.assertEqual(context["badge"], "PAID")
        self.assertEqual(context["paid"], Decimal("110.00"))
        self.assertEqual(context["amount_due"], Decimal("0.00"))
        self.assertIsNotNone(context["paid_at"])

    def test_partial_refund_shows_net_paid(self):
        invoice = self.make_invoice(status=Invoice.Status.PAID)
        self.pay(
            invoice, "110.00", refunded="30.00",
            status=Payment.Status.PARTIALLY_REFUNDED,
        )

        context = build_invoice_pdf_context(invoice)

        self.assertEqual(context["badge"], "PARTIALLY REFUNDED")
        self.assertEqual(context["refunded"], Decimal("30.00"))
        self.assertEqual(context["net_paid"], Decimal("80.00"))

        html = self.render(invoice)
        self.assertIn("Refunded", html)
        self.assertIn("USD 80.00", html)

    def test_full_refund_badge(self):
        invoice = self.make_invoice(status=Invoice.Status.PAID)
        self.pay(
            invoice, "110.00", refunded="110.00",
            status=Payment.Status.REFUNDED,
        )

        self.assertEqual(
            build_invoice_pdf_context(invoice)["badge"], "REFUNDED",
        )

    def test_void_invoice_has_no_amount_due_line(self):
        html = self.render(self.make_invoice(status=Invoice.Status.VOID))

        self.assertIn("has been voided", html)
        self.assertNotIn("Amount due", html)

    def test_missing_due_date_is_not_printed_as_none(self):
        html = self.render(self.make_invoice(due_date=None))

        self.assertNotIn("None", html)
        self.assertNotIn("Due date", html)

    def test_amounts_carry_currency(self):
        html = self.render(self.make_invoice())

        self.assertIn("USD 110.00", html)

    def test_pdf_is_generated(self):
        pdf = generate_invoice_pdf(self.make_invoice())

        self.assertTrue(pdf.startswith(b"%PDF"))
