from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.tenants.models import Membership, Organization
from apps.notifications.models import Notification

from .serializers import InvoiceSerializer
from .services import generate_invoice_pdf, send_invoice_email


from .models import (
    DunningAttempt,
    Invoice,
    InvoiceItem,
)

from .dunning import (
    create_dunning_attempt,
    get_due_dunning_attempt,
    process_overdue_invoices,
)

from .tasks import process_dunning_attempts



class InvoiceTestBase(APITestCase):

    def setUp(self):
        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="TestPassword123",
            first_name="Owner",
            last_name="User",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123",
            first_name="Admin",
            last_name="User",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123",
            first_name="Member",
            last_name="User",
        )

        self.accountant = User.objects.create_user(
            email="accountant@example.com",
            password="TestPassword123",
            first_name="Accountant",
            last_name="User",
        )

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123",
            first_name="Other",
            last_name="Owner",
        )

        # ---------------------------------------------------------
        # Organization 1
        # ---------------------------------------------------------

        self.organization = Organization.objects.create(
            name="Acme Corporation",
            slug="acme-corporation",
            billing_email="billing@acme.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        )

        Membership.objects.create(
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.accountant,
            organization=self.organization,
            role=Membership.Role.ACCOUNTANT,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Organization 2
        # ---------------------------------------------------------

        self.other_organization = Organization.objects.create(
            name="Other Corporation",
            slug="other-corporation",
            billing_email="billing@other.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Invoice
        # ---------------------------------------------------------

        self.invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number="INV-000001",
            status=Invoice.Status.DRAFT,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            billing_email="customer@example.com",
        )

        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            description="Monthly Subscription",
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
        )

        # ---------------------------------------------------------
        # Other tenant invoice
        # ---------------------------------------------------------

        self.other_invoice = Invoice.objects.create(
            organization=self.other_organization,
            invoice_number="INV-000001",
            status=Invoice.Status.DRAFT,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("200.00"),
            tax=Decimal("20.00"),
            total=Decimal("220.00"),
            billing_email="other@example.com",
        )

    # -------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------

    def authenticate(self, user):
        response = self.client.post(
            reverse("login"),
            {
                "email": user.email,
                "password": "TestPassword123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {response.data['tokens']['access']}"
            )
        )

    def clear_auth(self):
        self.client.credentials()

    # -------------------------------------------------------------
    # URL helpers
    # -------------------------------------------------------------

    def list_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "invoice-list-create",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def detail_url(
        self,
        invoice=None,
        organization=None,
    ):
        invoice = invoice or self.invoice
        organization = organization or invoice.organization

        return reverse(
            "invoice-detail",
            kwargs={
                "organization_id": organization.id,
                "invoice_id": invoice.id,
            },
        )

    def pdf_url(
        self,
        invoice=None,
        organization=None,
    ):
        invoice = invoice or self.invoice
        organization = organization or invoice.organization

        return reverse(
            "invoice-pdf",
            kwargs={
                "organization_id": organization.id,
                "invoice_id": invoice.id,
            },
        )

    def send_url(
        self,
        invoice=None,
        organization=None,
    ):
        invoice = invoice or self.invoice
        organization = organization or invoice.organization

        return reverse(
            "invoice-send",
            kwargs={
                "organization_id": organization.id,
                "invoice_id": invoice.id,
            },
        )


class InvoiceModelTests(InvoiceTestBase):

    def test_invoice_string_representation(self):
        self.assertEqual(
            str(self.invoice),
            "INV-000001 - Acme Corporation",
        )

    def test_invoice_item_amount_is_calculated_on_save(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            description="Extra Usage",
            quantity=Decimal("3.00"),
            unit_price=Decimal("25.00"),
        )

        self.assertEqual(
            item.amount,
            Decimal("75.00"),
        )

    def test_invoice_item_amount_updates_when_quantity_changes(self):
        self.item.quantity = Decimal("4.00")
        self.item.save()

        self.item.refresh_from_db()

        self.assertEqual(
            self.item.amount,
            Decimal("200.00"),
        )

    def test_invoice_item_amount_updates_when_price_changes(self):
        self.item.unit_price = Decimal("75.00")
        self.item.save()

        self.item.refresh_from_db()

        self.assertEqual(
            self.item.amount,
            Decimal("150.00"),
        )


class InvoiceSerializerTests(InvoiceTestBase):

    def test_quantity_must_be_greater_than_zero(self):
        serializer = InvoiceSerializer(
            data={
                "issue_date": str(date.today()),
                "billing_email": "customer@example.com",
                "items": [
                    {
                        "description": "Invalid",
                        "quantity": "0",
                        "unit_price": "10.00",
                    }
                ],
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Quantity must be greater than zero.",
            str(serializer.errors),
        )

    def test_negative_unit_price_is_rejected(self):
        serializer = InvoiceSerializer(
            data={
                "issue_date": str(date.today()),
                "billing_email": "customer@example.com",
                "items": [
                    {
                        "description": "Invalid",
                        "quantity": "1",
                        "unit_price": "-10.00",
                    }
                ],
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Unit price cannot be negative.",
            str(serializer.errors),
        )

    def test_draft_to_open_transition_is_allowed(self):
        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.OPEN,
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_open_to_paid_transition_is_allowed(self):
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save(update_fields=["status"])

        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.PAID,
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_open_to_void_transition_is_allowed(self):
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save(update_fields=["status"])

        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.VOID,
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_open_to_uncollectible_transition_is_allowed(self):
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save(update_fields=["status"])

        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.UNCOLLECTIBLE,
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

    def test_draft_to_paid_is_rejected(self):
        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.PAID,
            },
            partial=True,
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "Cannot change invoice status from DRAFT to PAID.",
            str(serializer.errors),
        )

    def test_paid_invoice_cannot_change_status(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save(update_fields=["status"])

        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.VOID,
            },
            partial=True,
        )

        self.assertFalse(
            serializer.is_valid()
        )

    def test_same_status_is_idempotent(self):
        serializer = InvoiceSerializer(
            self.invoice,
            data={
                "status": Invoice.Status.DRAFT,
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )


class InvoiceCreationAPITests(InvoiceTestBase):

    def test_accountant_can_create_invoice(self):
        # Phase 4: invoice creation is limited to finance roles
        # (OWNER / ADMIN / ACCOUNTANT). Previously this test used a
        # MEMBER, which was the permission hole being closed.
        self.authenticate(self.accountant)

        response = self.client.post(
            self.list_url(),
            {
                "issue_date": str(date.today()),
                "due_date": str(
                    date.today() + timedelta(days=30)
                ),
                "currency": "USD",
                "tax": "10.00",
                "billing_email": "customer@example.com",
                "items": [
                    {
                        "description": "Subscription",
                        "quantity": "2.00",
                        "unit_price": "50.00",
                    },
                    {
                        "description": "API Usage",
                        "quantity": "3.00",
                        "unit_price": "10.00",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000002",
        )

        self.assertEqual(
            Decimal(str(response.data["subtotal"])),
            Decimal("130.00"),
        )

        self.assertEqual(
            Decimal(str(response.data["total"])),
            Decimal("140.00"),
        )

        self.assertEqual(
            len(response.data["items"]),
            2,
        )

    def test_owner_can_create_invoice(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url(),
            {
                "issue_date": str(date.today()),
                "currency": "PKR",
                "tax": "0.00",
                "billing_email": "customer@example.com",
                "items": [
                    {
                        "description": "Service",
                        "quantity": "1.00",
                        "unit_price": "5000.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000002",
        )

    def test_invoice_number_is_generated_per_organization(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url(),
            {
                "invoice_number": "HACKED-999",
                "issue_date": str(date.today()),
                "currency": "USD",
                "tax": "0.00",
                "billing_email": "customer@example.com",
                "items": [{"description": "Service", "quantity": 1, "unit_price": "10.00"}],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000002",
        )

    def test_second_organization_starts_invoice_number_at_one(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.list_url(self.other_organization),
            {
                "issue_date": str(date.today()),
                "currency": "USD",
                "tax": "0.00",
                "billing_email": "other@example.com",
                "items": [{"description": "Service", "quantity": 1, "unit_price": "10.00"}],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000002",
        )

    def test_client_cannot_choose_organization(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url(),
            {
                "organization": str(
                    self.other_organization.id
                ),
                "issue_date": str(date.today()),
                "currency": "USD",
                "tax": "0.00",
                "billing_email": "customer@example.com",
                "items": [{"description": "Service", "quantity": 1, "unit_price": "10.00"}],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        created_invoice = Invoice.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            created_invoice.organization_id,
            self.organization.id,
        )

    def test_invoice_total_includes_tax(self):
        self.authenticate(self.accountant)

        response = self.client.post(
            self.list_url(),
            {
                "issue_date": str(date.today()),
                "currency": "USD",
                "tax": "25.50",
                "billing_email": "customer@example.com",
                "items": [
                    {
                        "description": "Product",
                        "quantity": "2.00",
                        "unit_price": "100.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Decimal(str(response.data["subtotal"])),
            Decimal("200.00"),
        )

        self.assertEqual(
            Decimal(str(response.data["total"])),
            Decimal("225.50"),
        )

    def test_unauthenticated_user_cannot_create_invoice(self):
        self.clear_auth()

        response = self.client.post(
            self.list_url(),
            {
                "issue_date": str(date.today()),
                "billing_email": "customer@example.com",
                "items": [],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_cross_tenant_user_cannot_create_invoice(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.list_url(self.organization),
            {
                "issue_date": str(date.today()),
                "billing_email": "customer@example.com",
                "items": [],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class InvoiceListTests(InvoiceTestBase):

    def test_member_can_list_invoices(self):
        self.authenticate(self.member)

        response = self.client.get(
            self.list_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["invoice_number"],
            "INV-000001",
        )

    def test_cross_tenant_invoice_list_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.list_url(self.organization)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_list_invoices(self):
        self.clear_auth()

        response = self.client.get(
            self.list_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_invoice_list_only_returns_current_organization(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.list_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        invoice_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            str(self.invoice.id),
            invoice_ids,
        )

        self.assertNotIn(
            str(self.other_invoice.id),
            invoice_ids,
        )


class InvoiceDetailTests(InvoiceTestBase):

    def test_admin_can_view_invoice_detail(self):
        self.authenticate(self.admin)

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000001",
        )

        self.assertEqual(
            len(response.data["items"]),
            1,
        )

    def test_owner_can_view_invoice_detail(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_member_cannot_view_invoice_detail(self):
        self.authenticate(self.member)

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_cannot_patch_invoice(self):
        self.authenticate(self.member)

        response = self.client.patch(
            self.detail_url(),
            {
                "status": "OPEN",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_patch_invoice_status(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(),
            {
                "status": "OPEN",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.Status.OPEN,
        )

    def test_cross_tenant_invoice_detail_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.detail_url(
                invoice=self.invoice,
                organization=self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_view_invoice_detail(self):
        self.clear_auth()

        response = self.client.get(
            self.detail_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class InvoicePDFTests(InvoiceTestBase):

    @patch(
        "apps.invoices.views.generate_invoice_pdf",
        return_value=b"%PDF-TEST-DATA",
    )
    def test_member_can_download_invoice_pdf(
        self,
        mock_generate,
    ):
        self.authenticate(self.member)

        response = self.client.get(
            self.pdf_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )

        self.assertIn(
            "INV-000001.pdf",
            response["Content-Disposition"],
        )

        self.assertEqual(
            response.content,
            b"%PDF-TEST-DATA",
        )

        mock_generate.assert_called_once()

    @patch(
        "apps.invoices.views.generate_invoice_pdf",
        return_value=b"%PDF-TEST-DATA",
    )
    def test_cross_tenant_user_cannot_download_pdf(
        self,
        mock_generate,
    ):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.pdf_url(
                invoice=self.invoice,
                organization=self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        mock_generate.assert_not_called()

    def test_unauthenticated_user_cannot_download_pdf(self):
        self.clear_auth()

        response = self.client.get(
            self.pdf_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch(
        "apps.invoices.services.HTML"
    )
    def test_generate_invoice_pdf_returns_bytes(
        self,
        mock_html,
    ):
        mock_html.return_value.write_pdf.return_value = (
            b"%PDF-TEST"
        )

        pdf = generate_invoice_pdf(
            self.invoice
        )

        self.assertEqual(
            pdf,
            b"%PDF-TEST",
        )


class InvoiceEmailServiceTests(InvoiceTestBase):

    def test_send_invoice_email_sends_pdf_attachment(self):
        mail.outbox = []

        result = send_invoice_email(
            self.invoice,
            b"%PDF-TEST",
        )

        self.assertTrue(result)

        self.assertEqual(
            len(mail.outbox),
            1,
        )

        email = mail.outbox[0]

        self.assertEqual(
            email.subject,
            "Invoice INV-000001",
        )

        self.assertEqual(
            email.to,
            ["customer@example.com"],
        )

        self.assertEqual(
            len(email.attachments),
            1,
        )

        filename, content, mimetype = email.attachments[0]

        self.assertEqual(
            filename,
            "INV-000001.pdf",
        )

        self.assertEqual(
            content,
            b"%PDF-TEST",
        )

        self.assertEqual(
            mimetype,
            "application/pdf",
        )


class InvoiceSendTests(InvoiceTestBase):

    @patch(
        "apps.invoices.views.send_invoice_email_task.delay"
    )
    def test_admin_can_send_draft_invoice(
        self,
        mock_delay,
    ):
        self.authenticate(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.send_url()
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            response.data["status"],
            Invoice.Status.OPEN,
        )

        self.assertEqual(
            response.data["invoice_number"],
            "INV-000001",
        )

        self.invoice.refresh_from_db()

        self.assertEqual(
            self.invoice.status,
            Invoice.Status.OPEN,
        )

        mock_delay.assert_called_once_with(
            str(self.invoice.id)
        )

 


    @patch(
        "apps.invoices.views.send_invoice_email_task.delay"
    )
    def test_owner_can_send_draft_invoice(
        self,
        mock_delay,
    ):
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.send_url()
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        mock_delay.assert_called_once()

    def test_member_cannot_send_invoice(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.send_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_send_invoice(self):
        self.clear_auth()

        response = self.client.post(
            self.send_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_open_invoice_can_be_sent_again(self, mock_delay):
        # Unpaid invoices can be re-sent (see test_invoice_sending.py).
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save(update_fields=["status"])

        self.authenticate(self.owner)

        response = self.client.post(
            self.send_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

    def test_paid_invoice_cannot_be_sent(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save(update_fields=["status"])

        self.authenticate(self.owner)

        response = self.client.post(
            self.send_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cross_tenant_invoice_cannot_be_sent(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.send_url(
                invoice=self.invoice,
                organization=self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @patch(
        "apps.invoices.views.send_invoice_email_task.delay"
    )
    def test_send_invoice_returns_billing_email(
        self,
        mock_delay,
    ):
        self.authenticate(self.owner)

        response = self.client.post(
            self.send_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            response.data["billing_email"],
            "customer@example.com",
        )


class InvoiceTaskTests(InvoiceTestBase):

    @patch("apps.invoices.tasks.send_invoice_email")
    @patch("apps.invoices.tasks.generate_invoice_pdf")
    def test_send_invoice_email_task_returns_success(
        self,
        mock_pdf,
        mock_email,
    ):
        from .tasks import send_invoice_email_task

        mock_pdf.return_value = b"%PDF-TEST"

        result = send_invoice_email_task.run(
            str(self.invoice.id)
        )

        self.assertEqual(
            result,
            {
                "invoice_id": str(self.invoice.id),
                "invoice_number": "INV-000001",
                "status": "sent",
            },
        )

        mock_pdf.assert_called_once()
        mock_email.assert_called_once_with(
            invoice=self.invoice,
            pdf=b"%PDF-TEST",
        )


class DunningServiceTests(InvoiceTestBase):

    def make_overdue_invoice(self, days_overdue):
        invoice = Invoice.objects.create(
            organization=self.organization,
            invoice_number=f"INV-DUNNING-{days_overdue}",
            status=Invoice.Status.OPEN,
            issue_date=(
                date.today()
                - timedelta(days=days_overdue + 10)
            ),
            due_date=(
                date.today()
                - timedelta(days=days_overdue)
            ),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            billing_email="customer@example.com",
        )

        return invoice

    def test_first_reminder_is_due_after_one_day(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        result = get_due_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertEqual(
            result,
            (
                1,
                DunningAttempt.AttemptType.FIRST_REMINDER,
            ),
        )

    def test_second_reminder_is_due_after_three_days(self):
        invoice = self.make_overdue_invoice(
            days_overdue=3,
        )

        result = get_due_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertEqual(
            result,
            (
                2,
                DunningAttempt.AttemptType.SECOND_REMINDER,
            ),
        )

    def test_final_reminder_is_due_after_seven_days(self):
        invoice = self.make_overdue_invoice(
            days_overdue=7,
        )

        result = get_due_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertEqual(
            result,
            (
                3,
                DunningAttempt.AttemptType.FINAL_REMINDER,
            ),
        )

    def test_dunning_is_not_due_before_one_day(self):
        invoice = self.make_overdue_invoice(
            days_overdue=0,
        )

        result = get_due_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertIsNone(result)

    def test_paid_invoice_is_not_processed(self):
        invoice = self.make_overdue_invoice(
            days_overdue=7,
        )

        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        result = get_due_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertIsNone(result)

    def test_first_dunning_attempt_is_created(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertIsNotNone(attempt)

        self.assertEqual(
            attempt.attempt_number,
            1,
        )

        self.assertEqual(
            attempt.attempt_type,
            DunningAttempt.AttemptType.FIRST_REMINDER,
        )

        self.assertEqual(
            attempt.status,
            DunningAttempt.Status.PENDING,
        )

    def test_same_dunning_attempt_is_not_created_twice(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        first_attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        second_attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        self.assertEqual(
            first_attempt.id,
            second_attempt.id,
        )

        self.assertEqual(
            DunningAttempt.objects.filter(
                invoice=invoice,
            ).count(),
            1,
        )

    def test_process_overdue_invoices_creates_attempts(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        processed_count = process_overdue_invoices(
            today=date.today(),
        )

        self.assertEqual(
            processed_count,
            1,
        )

        self.assertTrue(
            DunningAttempt.objects.filter(
                invoice=invoice,
                attempt_number=1,
            ).exists()
        )

    def test_dunning_is_tenant_scoped(self):
        invoice = Invoice.objects.create(
            organization=self.other_organization,
            invoice_number="INV-OTHER-DUNNING",
            status=Invoice.Status.OPEN,
            issue_date=(
                date.today()
                - timedelta(days=10)
            ),
            due_date=(
                date.today()
                - timedelta(days=7)
            ),
            currency=Invoice.Currency.USD,
            subtotal=Decimal("200.00"),
            tax=Decimal("20.00"),
            total=Decimal("220.00"),
            billing_email="other@example.com",
        )

        process_overdue_invoices(
            today=date.today(),
        )

        attempt = DunningAttempt.objects.get(
            invoice=invoice,
        )

        self.assertEqual(
            attempt.organization,
            self.other_organization,
        )

    def test_process_dunning_attempt_sends_email_and_marks_sent(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        result = process_dunning_attempts.run()

        attempt.refresh_from_db()

        self.assertEqual(
            result["processed"],
            1,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        self.assertEqual(
            attempt.status,
            DunningAttempt.Status.SENT,
        )

        self.assertIsNotNone(
            attempt.sent_at,
        )

        self.assertEqual(
            len(mail.outbox),
            1,
        )

        self.assertEqual(
            mail.outbox[0].to,
            [invoice.billing_email],
        )

        self.assertIn(
            invoice.invoice_number,
            mail.outbox[0].subject,
        )


    def test_process_dunning_attempt_creates_in_app_notification(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        invoice.billing_email = self.owner.email
        invoice.save(
            update_fields=["billing_email"],
        )

        create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        result = process_dunning_attempts.run()

        self.assertEqual(
            result["processed"],
            1,
        )

        notification = Notification.objects.get(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.INVOICE_OVERDUE,
        )

        self.assertIn(
            invoice.invoice_number,
            notification.message,
        )


    def test_paid_invoice_dunning_attempt_is_not_sent(self):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        invoice.status = Invoice.Status.PAID
        invoice.save(
            update_fields=["status"],
        )

        result = process_dunning_attempts.run()

        attempt.refresh_from_db()

        self.assertEqual(
            result["processed"],
            0,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        self.assertEqual(
            attempt.status,
            DunningAttempt.Status.FAILED,
        )

        self.assertEqual(
            attempt.error_message,
            "Invoice is no longer open.",
        )

        self.assertEqual(
            len(mail.outbox),
            0,
        )


    @patch(
        "apps.invoices.tasks.send_dunning_reminder_email",
        side_effect=Exception("Email service unavailable"),
    )
    def test_failed_dunning_email_marks_attempt_failed(
        self,
        mock_send_email,
    ):
        invoice = self.make_overdue_invoice(
            days_overdue=1,
        )

        attempt = create_dunning_attempt(
            invoice,
            today=date.today(),
        )

        result = process_dunning_attempts.run()

        attempt.refresh_from_db()

        self.assertEqual(
            result["processed"],
            0,
        )

        self.assertEqual(
            result["failed"],
            1,
        )

        self.assertEqual(
            attempt.status,
            DunningAttempt.Status.FAILED,
        )

        self.assertIsNotNone(
            attempt.failed_at,
        )

        self.assertEqual(
            attempt.error_message,
            "Email service unavailable",
        )

        mock_send_email.assert_called_once()

# =============================================================================
# ROLES + INVOICE INTEGRITY — Phase 4
# =============================================================================


class InvoiceRolePermissionTests(InvoiceTestBase):

    def new_invoice_payload(self, **extra):
        payload = {
            "issue_date": str(date.today()),
            "currency": "USD",
            "tax": "0.00",
            "billing_email": "customer@example.com",
            "items": [
                {
                    "description": "Service",
                    "quantity": "1.00",
                    "unit_price": "100.00",
                }
            ],
        }
        payload.update(extra)
        return payload

    def test_member_cannot_create_invoice(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url(),
            self.new_invoice_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_can_still_list_invoices(self):
        self.authenticate(self.member)

        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_accountant_can_view_and_edit_draft(self):
        self.authenticate(self.accountant)

        response = self.client.get(self.detail_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            self.detail_url(),
            {"due_date": str(date.today() + timedelta(days=10))},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.invoices.views.send_invoice_email_task.delay")
    def test_accountant_can_send_invoice(self, mock_delay):
        self.authenticate(self.accountant)

        response = self.client.post(
            reverse(
                "invoice-send",
                kwargs={
                    "organization_id": self.organization.id,
                    "invoice_id": self.invoice.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

    @patch("apps.invoices.views.stripe.checkout.Session.create")
    def test_member_cannot_start_invoice_payment(self, mock_create):
        from types import SimpleNamespace

        mock_create.return_value = SimpleNamespace(
            id="cs_test_member",
            url="https://checkout.stripe.com/member",
        )

        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save()

        self.authenticate(self.member)

        response = self.client.post(
            reverse(
                "invoice-pay",
                kwargs={
                    "organization_id": self.organization.id,
                    "invoice_id": self.invoice.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        mock_create.assert_not_called()

    def test_cannot_create_invoice_as_paid(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url(),
            self.new_invoice_payload(status="PAID"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("status", response.data)

    def test_negative_tax_is_rejected(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url(),
            self.new_invoice_payload(tax="-5.00"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class InvoiceIntegrityTests(InvoiceTestBase):

    def set_items(self, *items):
        self.invoice.items.all().delete()
        for description, quantity, unit_price in items:
            InvoiceItem.objects.create(
                invoice=self.invoice,
                description=description,
                quantity=Decimal(quantity),
                unit_price=Decimal(unit_price),
            )
        self.invoice.subtotal = sum(
            (i.amount for i in self.invoice.items.all()),
            Decimal("0.00"),
        )
        self.invoice.total = self.invoice.subtotal + self.invoice.tax
        self.invoice.save()

    def test_changing_tax_on_draft_recalculates_total(self):
        self.set_items(("Service", "2.00", "50.00"))
        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(),
            {"tax": "15.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))
        self.assertEqual(self.invoice.total, Decimal("115.00"))

    def test_replacing_items_on_draft_recalculates_totals(self):
        self.set_items(("Old", "1.00", "10.00"))
        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(),
            {
                "tax": "5.00",
                "items": [
                    {
                        "description": "New A",
                        "quantity": "3.00",
                        "unit_price": "20.00",
                    },
                    {
                        "description": "New B",
                        "quantity": "1.00",
                        "unit_price": "40.00",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.items.count(), 2)
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))
        self.assertEqual(self.invoice.total, Decimal("105.00"))

    def test_open_invoice_amounts_are_locked(self):
        self.set_items(("Service", "1.00", "100.00"))
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save()
        total_before = self.invoice.total

        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(),
            {"tax": "50.00"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("tax", response.data)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total, total_before)

    def test_paid_invoice_billing_email_is_locked(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save()

        self.authenticate(self.owner)

        response = self.client.patch(
            self.detail_url(),
            {"billing_email": "changed@example.com"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_manual_mark_paid_is_audited(self):
        from apps.audit.models import AuditLog

        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save()

        self.authenticate(self.accountant)

        response = self.client.patch(
            self.detail_url(),
            {"status": "PAID"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        log = AuditLog.objects.get(
            organization=self.organization,
            action="INVOICE_MARKED_PAID",
        )
        self.assertEqual(log.user, self.accountant)
        self.assertEqual(log.metadata["previous_status"], "OPEN")

    def test_open_invoice_status_change_does_not_touch_totals(self):
        self.invoice.status = Invoice.Status.OPEN
        self.invoice.subtotal = Decimal("80.00")
        self.invoice.total = Decimal("88.00")
        self.invoice.tax = Decimal("8.00")
        self.invoice.save()

        self.authenticate(self.admin)

        response = self.client.patch(
            self.detail_url(),
            {"status": "VOID"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)
        self.assertEqual(self.invoice.total, Decimal("88.00"))


# =============================================================================
# DUNNING SCHEDULE — Phase 3
# =============================================================================


class DunningScheduleTests(SimpleTestCase):
    """
    process_overdue_invoices used to exist only in tests: nothing in
    Celery Beat called it, so dunning attempts were never created.
    """

    def test_beat_schedule_creates_attempts_before_sending(self):
        from django.conf import settings

        schedule = settings.CELERY_BEAT_SCHEDULE

        tasks = {entry["task"]: entry for entry in schedule.values()}

        self.assertIn(
            "apps.invoices.tasks.create_due_dunning_attempts",
            tasks,
        )
        self.assertIn(
            "apps.invoices.tasks.process_dunning_attempts",
            tasks,
        )

        create_minute = tasks[
            "apps.invoices.tasks.create_due_dunning_attempts"
        ]["schedule"].minute
        send_minute = tasks[
            "apps.invoices.tasks.process_dunning_attempts"
        ]["schedule"].minute

        self.assertLess(min(create_minute), min(send_minute))

    @patch("apps.invoices.dunning.process_overdue_invoices")
    def test_task_calls_process_overdue_invoices(self, mock_process):
        from apps.invoices.tasks import create_due_dunning_attempts

        mock_process.return_value = 4

        self.assertEqual(create_due_dunning_attempts(), 4)
        mock_process.assert_called_once_with()


# =============================================================================
# PAYMENTS — Phase 5
# =============================================================================


class PaymentRecordingTests(InvoiceTestBase):

    def payments_url(self, organization=None):
        organization = organization or self.organization
        return reverse(
            "payment-list",
            kwargs={"organization_id": organization.id},
        )

    def test_manual_mark_paid_records_manual_payment(self):
        from .models import Payment

        self.invoice.status = Invoice.Status.OPEN
        self.invoice.total = Decimal("75.00")
        self.invoice.save()

        self.authenticate(self.accountant)

        response = self.client.patch(
            self.detail_url(),
            {"status": "PAID"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment = Payment.objects.get(invoice=self.invoice)
        self.assertEqual(payment.method, Payment.Method.MANUAL)
        self.assertEqual(payment.amount, Decimal("75.00"))
        self.assertEqual(payment.recorded_by, self.accountant)

    def test_voiding_invoice_records_no_payment(self):
        from .models import Payment

        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save()

        self.authenticate(self.admin)

        self.client.patch(
            self.detail_url(),
            {"status": "VOID"},
            format="json",
        )

        self.assertFalse(Payment.objects.exists())

    def test_finance_can_list_payments_tenant_scoped(self):
        from django.utils import timezone

        from .models import Payment

        Payment.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            amount=Decimal("10.00"),
            method=Payment.Method.MANUAL,
            paid_at=timezone.now(),
        )
        Payment.objects.create(
            organization=self.other_organization,
            amount=Decimal("99.00"),
            method=Payment.Method.MANUAL,
            paid_at=timezone.now(),
        )

        self.authenticate(self.accountant)

        response = self.client.get(self.payments_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["amount"], "10.00")
        self.assertEqual(
            response.data[0]["invoice_number"],
            self.invoice.invoice_number,
        )

    def test_member_cannot_list_payments(self):
        self.authenticate(self.member)

        response = self.client.get(self.payments_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_other_tenant_cannot_list_payments(self):
        self.authenticate(self.other_owner)

        response = self.client.get(self.payments_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# BACKFILL COMMAND — Phase 6
# =============================================================================


class BackfillPaymentsCommandTests(InvoiceTestBase):

    def run_command(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("backfill_payments", *args, stdout=out)
        return out.getvalue()

    def test_local_paid_invoice_gets_one_manual_payment(self):
        from .models import Payment

        self.invoice.status = Invoice.Status.PAID
        self.invoice.total = Decimal("60.00")
        self.invoice.save()

        self.run_command("--skip-stripe")
        self.run_command("--skip-stripe")

        payment = Payment.objects.get(invoice=self.invoice)
        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertEqual(payment.method, Payment.Method.MANUAL)

    def test_dry_run_saves_nothing(self):
        from .models import Payment

        self.invoice.status = Invoice.Status.PAID
        self.invoice.save()

        output = self.run_command("--skip-stripe", "--dry-run")

        self.assertIn("would record", output)
        self.assertFalse(Payment.objects.exists())

    def test_open_invoice_is_not_backfilled(self):
        from .models import Payment

        self.invoice.status = Invoice.Status.OPEN
        self.invoice.save()

        self.run_command("--skip-stripe")

        self.assertFalse(Payment.objects.exists())

    @patch("apps.invoices.management.commands.backfill_payments.stripe.Invoice.list")
    def test_stripe_paid_invoices_are_imported_once(self, mock_list):
        from unittest.mock import MagicMock

        from apps.billing.models import Plan, Subscription

        from .models import Payment

        plan = Plan.objects.create(code="PRO", name="Pro")
        Subscription.objects.create(
            organization=self.organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            stripe_subscription_id="sub_backfill",
        )

        data = {
            "id": "in_backfill_1",
            "number": "BF-0001",
            "currency": "usd",
            "created": 1798932600,
            "total": 2900,
            "amount_paid": 2900,
            "total_taxes": [],
            "status_transitions": {"paid_at": 1798932700},
            "parent": {"subscription_details": {
                "subscription": "sub_backfill",
            }},
            "lines": {"data": [
                {"description": "Pro", "amount": 2900, "quantity": 1},
            ]},
        }

        orphan = dict(data, id="in_orphan", parent={
            "subscription_details": {"subscription": "sub_unknown"},
        })

        def fake_list(**kwargs):
            items = []
            for d in (data, orphan):
                obj = MagicMock()
                obj.to_dict.return_value = d
                items.append(obj)
            result = MagicMock()
            result.auto_paging_iter.return_value = iter(items)
            return result

        mock_list.side_effect = fake_list

        output = self.run_command("--skip-local")
        self.assertIn("1 imported", output)
        self.assertIn("1 skipped (no organization)", output)

        output = self.run_command("--skip-local")
        self.assertIn("0 imported", output)
        self.assertIn("1 already present", output)

        self.assertEqual(
            Payment.objects.get().amount,
            Decimal("29.00"),
        )
        mock_list.assert_called_with(status="paid", limit=100)
