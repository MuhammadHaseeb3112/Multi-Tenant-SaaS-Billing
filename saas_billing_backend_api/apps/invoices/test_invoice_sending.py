from datetime import date, timedelta
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog

from .models import Invoice
from .public import make_payment_token
from .tests import InvoiceTestBase


@override_settings(FRONTEND_URL="https://app.example.com")
class InvoiceSendingTests(APITestCase):
    """Auto-send on create, re-sending, and old payment links expiring."""

    setUp = InvoiceTestBase.setUp
    authenticate = InvoiceTestBase.authenticate

    def list_url(self):
        return reverse(
            "invoice-list-create",
            kwargs={"organization_id": self.organization.id},
        )

    def send_url(self):
        return reverse(
            "invoice-send",
            kwargs={
                "organization_id": self.organization.id,
                "invoice_id": self.invoice.id,
            },
        )

    def public_url(self, token):
        return reverse("public-invoice", kwargs={"token": token})

    def public_pay_url(self, token):
        return reverse("public-invoice-pay", kwargs={"token": token})

    def payload(self, **extra):
        data = {
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=7)),
            "currency": "USD",
            "tax": "0.00",
            "billing_email": "client@example.com",
            "items": [
                {"description": "Design", "quantity": 2, "unit_price": "35.00"}
            ],
        }
        data.update(extra)
        return data

    def send(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.send_url())

    # ---------------------------------------------------------- create

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_create_with_send_now_emails_customer(self, mock_delay):
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.list_url(),
                self.payload(send_now=True),
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "OPEN")
        self.assertEqual(response.data["sent_count"], 1)
        self.assertIsNotNone(response.data["last_sent_at"])
        mock_delay.assert_called_once_with(response.data["id"])

        actions = set(
            AuditLog.objects
            .filter(resource_id=response.data["id"])
            .values_list("action", flat=True)
        )
        self.assertEqual(actions, {"INVOICE_CREATED", "INVOICE_SENT"})

        created = AuditLog.objects.get(
            resource_id=response.data["id"],
            action="INVOICE_CREATED",
        )
        self.assertIn("(USD 70.00)", created.description)

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_create_without_send_now_stays_draft(self, mock_delay):
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.list_url(),
                self.payload(),
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertEqual(response.data["sent_count"], 0)
        mock_delay.assert_not_called()

    # ---------------------------------------------------------- resend

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_unpaid_invoice_can_be_sent_many_times(self, mock_delay):
        self.authenticate(self.owner)

        first = self.send()
        second = self.send()
        third = self.send()

        for response in (first, second, third):
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        self.assertEqual(third.data["sent_count"], 3)
        self.assertEqual(mock_delay.call_count, 3)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.OPEN)
        self.assertEqual(
            AuditLog.objects.filter(action="INVOICE_RESENT").count(),
            2,
        )

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_resending_expires_older_payment_links(self, mock_delay):
        self.authenticate(self.owner)

        self.send()
        self.invoice.refresh_from_db()
        old_token = make_payment_token(self.invoice)

        self.send()
        self.invoice.refresh_from_db()
        new_token = make_payment_token(self.invoice)

        self.client.credentials()  # the customer is not logged in

        old = self.client.get(self.public_url(old_token))
        self.assertEqual(old.status_code, status.HTTP_410_GONE)
        self.assertEqual(old.data["code"], "link_replaced")

        old_pay = self.client.post(self.public_pay_url(old_token))
        self.assertEqual(old_pay.status_code, status.HTTP_410_GONE)

        new = self.client.get(self.public_url(new_token))
        self.assertEqual(new.status_code, status.HTTP_200_OK)
        self.assertTrue(new.data["payable"])

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_paid_invoice_shows_paid_on_old_links(self, mock_delay):
        self.authenticate(self.owner)
        self.send()
        self.invoice.refresh_from_db()
        old_token = make_payment_token(self.invoice)
        self.send()

        Invoice.objects.filter(pk=self.invoice.pk).update(
            status=Invoice.Status.PAID,
        )

        self.client.credentials()
        response = self.client.get(self.public_url(old_token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PAID")
        self.assertFalse(response.data["payable"])

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_paid_invoice_cannot_be_sent(self, mock_delay):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save()
        self.authenticate(self.owner)

        response = self.send()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be sent", response.data["detail"])
        mock_delay.assert_not_called()

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_member_cannot_send(self, mock_delay):
        self.authenticate(self.member)

        response = self.send()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_delay.assert_not_called()


@override_settings(FRONTEND_URL="https://app.example.com")
class ZeroInvoiceTests(APITestCase):
    """An invoice must bill something before it exists or is sent."""

    setUp = InvoiceTestBase.setUp
    authenticate = InvoiceTestBase.authenticate
    list_url = InvoiceSendingTests.list_url
    send_url = InvoiceSendingTests.send_url
    payload = InvoiceSendingTests.payload

    def create(self, **extra):
        self.authenticate(self.owner)
        return self.client.post(
            self.list_url(), self.payload(**extra), format="json",
        )

    def test_invoice_without_items_is_rejected(self):
        before = Invoice.objects.count()

        response = self.create(items=[])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at least one invoice item", str(response.data))
        self.assertEqual(Invoice.objects.count(), before)

    def test_zero_total_invoice_is_rejected(self):
        before = Invoice.objects.count()

        response = self.create(
            items=[{"description": "Free", "quantity": 1, "unit_price": "0"}],
            send_now=True,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("greater than zero", str(response.data))
        self.assertEqual(Invoice.objects.count(), before)

    def test_tax_alone_cannot_be_invoiced(self):
        before = Invoice.objects.count()

        response = self.create(
            items=[{"description": "Free", "quantity": 1, "unit_price": "0"}],
            tax="40.00",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Tax alone", str(response.data))
        self.assertEqual(Invoice.objects.count(), before)

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_existing_tax_only_draft_cannot_be_sent(self, mock_delay):
        Invoice.objects.filter(pk=self.invoice.pk).update(
            subtotal=0, tax=40, total=40,
        )
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.send_url())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_delay.assert_not_called()

    def test_free_line_is_fine_when_the_total_is_positive(self):
        response = self.create(
            items=[
                {"description": "Setup", "quantity": 1, "unit_price": "0"},
                {"description": "Design", "quantity": 1, "unit_price": "50"},
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total"], "50.00")

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_existing_zero_invoice_cannot_be_sent(self, mock_delay):
        Invoice.objects.filter(pk=self.invoice.pk).update(total=0)
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.send_url())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("greater than zero", response.data["detail"])
        mock_delay.assert_not_called()


class DeleteDraftInvoiceTests(APITestCase):
    """Drafts can be deleted; anything already sent can only be voided."""

    setUp = InvoiceTestBase.setUp
    authenticate = InvoiceTestBase.authenticate

    def url(self, invoice=None):
        return reverse(
            "invoice-detail",
            kwargs={
                "organization_id": self.organization.id,
                "invoice_id": (invoice or self.invoice).id,
            },
        )

    def test_draft_is_deleted_and_logged(self):
        self.authenticate(self.owner)
        invoice_id = str(self.invoice.id)

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Invoice.objects.filter(pk=invoice_id).exists())

        log = AuditLog.objects.get(action="INVOICE_DELETED")
        self.assertEqual(log.resource_id, invoice_id)
        self.assertEqual(log.user, self.owner)
        self.assertIn("INV-000001", log.description)

    def test_sent_or_paid_invoices_cannot_be_deleted(self):
        self.authenticate(self.owner)

        for state in (
            Invoice.Status.OPEN,
            Invoice.Status.PAID,
            Invoice.Status.VOID,
        ):
            Invoice.objects.filter(pk=self.invoice.pk).update(status=state)

            response = self.client.delete(self.url())

            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, state,
            )
            self.assertIn("Only draft", response.data["detail"])

        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())
        self.assertFalse(
            AuditLog.objects.filter(action="INVOICE_DELETED").exists()
        )

    def test_member_cannot_delete(self):
        self.authenticate(self.member)

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_other_organization_cannot_delete(self):
        self.authenticate(self.owner)

        response = self.client.delete(
            reverse(
                "invoice-detail",
                kwargs={
                    "organization_id": self.other_organization.id,
                    "invoice_id": self.invoice.id,
                },
            )
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())
