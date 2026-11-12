import stripe

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .tasks import send_invoice_email_task
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


from .services import (
    generate_invoice_pdf,
    send_invoice_email,
)

from apps.tenants.models import Organization
from apps.audit.services import create_audit_log
from apps.tenants.permissions import (
    IsOrganizationFinance,
    IsOrganizationMember,
)

from apps.accounts.security import AuthRateThrottle

from .models import Invoice, Payment
from .public import read_payment_token
from .payments import record_manual_payment
from .serializers import InvoiceSerializer, PaymentSerializer


def send_invoice_to_customer(invoice, user):
    """
    Email the invoice (PDF + payment link) to its billing email.

    DRAFT -> OPEN on the first send. OPEN invoices can be sent again
    until they are paid; each send moves payment_link_version on, so the
    payment links in earlier emails stop working.

    Returns an error message, or None when the email was queued. Must
    run inside a transaction (the email goes out after commit).
    """

    invoice = (
        Invoice.objects
        .select_for_update()
        .get(pk=invoice.pk)
    )

    if invoice.status not in (Invoice.Status.DRAFT, Invoice.Status.OPEN):
        return (
            f"A {invoice.status.lower()} invoice cannot be sent. "
            "Only draft or open invoices can be emailed."
        )

    if not invoice.billing_email:
        return "Invoice billing email is required."

    if invoice.subtotal <= 0 or invoice.total <= 0:
        return (
            "The invoice items must add up to an amount greater than "
            "zero. This invoice cannot be sent."
        )

    resend = invoice.sent_count > 0 or invoice.status == Invoice.Status.OPEN

    Invoice.objects.filter(pk=invoice.pk).update(
        status=Invoice.Status.OPEN,
        sent_count=F("sent_count") + 1,
        payment_link_version=F("payment_link_version") + 1,
        last_sent_at=timezone.now(),
        updated_at=timezone.now(),
    )
    invoice.refresh_from_db()

    create_audit_log(
        organization=invoice.organization,
        user=user,
        action="INVOICE_RESENT" if resend else "INVOICE_SENT",
        resource_type="Invoice",
        resource_id=invoice.id,
        description=(
            f"Invoice {invoice.invoice_number} "
            f"{'sent again' if resend else 'sent'} to "
            f"{invoice.billing_email}."
        ),
        metadata={
            "sent_count": invoice.sent_count,
            "billing_email": invoice.billing_email,
        },
    )

    invoice_id = str(invoice.id)
    transaction.on_commit(
        lambda: send_invoice_email_task.delay(invoice_id)
    )

    return None


class InvoiceListCreateView(APIView):
    """
    GET:  any organization member can list invoices.
    POST: only finance roles (OWNER, ADMIN, ACCOUNTANT) can create.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrganizationFinance()]

        return [IsAuthenticated(), IsOrganizationMember()]

    def get(self, request, organization_id):
        invoices = (
            Invoice.objects
            .filter(
                organization_id=organization_id,
            )
            .prefetch_related("items")
        )

        serializer = InvoiceSerializer(
            invoices,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def post(self, request, organization_id):
        serializer = InvoiceSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        # Optional: email the invoice to the customer straight away.
        send_now = serializers.BooleanField().to_internal_value(
            request.data.get("send_now", False)
        )

        organization = get_object_or_404(
            Organization,
            id=organization_id,
        )

        invoice = serializer.save(
            organization=organization,
        )

        create_audit_log(
            organization=organization,
            user=request.user,
            action="INVOICE_CREATED",
            resource_type="Invoice",
            resource_id=invoice.id,
            description=(
                f"Invoice {invoice.invoice_number} created for "
                f"{invoice.billing_email} "
                f"({invoice.currency} {invoice.total:.2f})."
            ),
        )

        if send_now:
            send_invoice_to_customer(invoice, request.user)
            invoice.refresh_from_db()

        return Response(
            InvoiceSerializer(invoice).data,
            status=status.HTTP_201_CREATED,
        )


class InvoiceDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationFinance,
    ]

    def get_object(
        self,
        organization_id,
        invoice_id,
    ):
        return get_object_or_404(
            Invoice.objects.prefetch_related("items"),
            id=invoice_id,
            organization_id=organization_id,
        )

    def get(
        self,
        request,
        organization_id,
        invoice_id,
    ):
        invoice = self.get_object(
            organization_id,
            invoice_id,
        )

        serializer = InvoiceSerializer(
            invoice,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(
        self,
        request,
        organization_id,
        invoice_id,
    ):
        invoice = self.get_object(
            organization_id,
            invoice_id,
        )

        previous_status = invoice.status

        serializer = InvoiceSerializer(
            invoice,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        invoice = serializer.save()

        # Every manual status change is recorded. Marking an invoice
        # PAID by hand means money arrived outside Stripe, so it must be
        # traceable to a person.
        if invoice.status != previous_status:
            if invoice.status == Invoice.Status.PAID:
                record_manual_payment(invoice, request.user)

            create_audit_log(
                organization=invoice.organization,
                user=request.user,
                action=f"INVOICE_MARKED_{invoice.status}",
                resource_type="Invoice",
                resource_id=invoice.id,
                description=(
                    f"Invoice {invoice.invoice_number} changed from "
                    f"{previous_status} to {invoice.status} manually."
                ),
                metadata={
                    "previous_status": previous_status,
                    "new_status": invoice.status,
                    "total": str(invoice.total),
                    "currency": invoice.currency,
                },
            )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    

    @transaction.atomic
    def delete(
        self,
        request,
        organization_id,
        invoice_id,
    ):
        """
        Delete a DRAFT invoice. A draft was never sent, so nothing
        outside the workspace refers to it. Anything already sent is
        part of the customer's records: it is voided, never deleted.
        """

        invoice = self.get_object(
            organization_id,
            invoice_id,
        )

        if invoice.status != Invoice.Status.DRAFT:
            return Response(
                {
                    "detail": (
                        "Only draft invoices can be deleted. "
                        "Void this invoice instead."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_audit_log(
            organization=invoice.organization,
            user=request.user,
            action="INVOICE_DELETED",
            resource_type="Invoice",
            resource_id=invoice.id,
            description=(
                f"Draft invoice {invoice.invoice_number} "
                f"({invoice.currency} {invoice.total:.2f}) deleted."
            ),
            metadata={
                "invoice_number": invoice.invoice_number,
                "billing_email": invoice.billing_email,
                "total": str(invoice.total),
            },
        )

        invoice.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

class InvoicePDFView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(
        self,
        request,
        organization_id,
        invoice_id,
    ):
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items"),
            id=invoice_id,
            organization_id=organization_id,
        )

        pdf = generate_invoice_pdf(
            invoice=invoice,
            request=request,
        )

        response = HttpResponse(
            pdf,
            content_type="application/pdf",
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.invoice_number}.pdf"'
        )

        return response




class InvoiceSendView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationFinance,
    ]

    @transaction.atomic
    def post(
        self,
        request,
        organization_id,
        invoice_id,
    ):
        invoice = get_object_or_404(
            Invoice,
            id=invoice_id,
            organization_id=organization_id,
        )

        error = send_invoice_to_customer(invoice, request.user)

        if error:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice.refresh_from_db()

        return Response(
            {
                "detail": "Invoice queued for email delivery.",
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "billing_email": invoice.billing_email,
                "sent_count": invoice.sent_count,
                "last_sent_at": invoice.last_sent_at,
            },
            status=status.HTTP_202_ACCEPTED,
        )



def payable_invoice_error(invoice):
    """Why this invoice cannot be paid now, or None if it can."""

    if invoice.status == Invoice.Status.PAID:
        return "This invoice has already been paid."

    if invoice.status != Invoice.Status.OPEN:
        return "Only open invoices can be paid."

    if invoice.total <= 0:
        return "Invoice total must be greater than zero."

    return None


def create_invoice_checkout_session(invoice, success_url, cancel_url):
    """
    One-time Stripe Checkout payment for the invoice total, in the
    invoice's own currency. The webhook marks the invoice PAID.
    """

    stripe.api_key = settings.STRIPE_SECRET_KEY

    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": invoice.currency.lower(),
                    "product_data": {
                        "name": f"Invoice {invoice.invoice_number}",
                    },
                    # Smallest currency unit (cents / pence).
                    "unit_amount": int(
                        (invoice.total * 100).to_integral_value()
                    ),
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=invoice.billing_email,
        metadata={
            "invoice_id": str(invoice.id),
            "organization_id": str(invoice.organization_id),
            "invoice_number": invoice.invoice_number,
            "payment_type": "invoice",
        },
    )


class InvoicePaymentView(APIView):
    """
    Create a Stripe Checkout Session for an open invoice.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationFinance,
    ]

    def post(self, request, organization_id, invoice_id):
        invoice = get_object_or_404(
            Invoice.objects.select_related("organization"),
            id=invoice_id,
            organization_id=organization_id,
        )

        error = payable_invoice_error(invoice)

        if error:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            checkout_session = create_invoice_checkout_session(
                invoice,
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
            )

        except stripe.error.StripeError:
            return Response(
                {"detail": "Stripe could not create the payment session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            },
            status=status.HTTP_201_CREATED,
        )

INVALID_LINK = "This payment link is not valid."
REPLACED_LINK = (
    "This payment link has expired because the invoice was emailed "
    "again. Please use the link in the latest email."
)


def public_invoice_for(token):
    """
    (invoice, None) for a working payment link, or (None, Response)
    explaining why it does not work.
    """

    data = read_payment_token(token)

    invoice = None
    if data:
        invoice_id, version = data
        invoice = (
            Invoice.objects
            .select_related("organization")
            .prefetch_related("items")
            .filter(id=invoice_id, organization__is_active=True)
            .first()
        )

    if not invoice:
        return None, Response(
            {"detail": INVALID_LINK},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Paid invoices keep showing as paid on any of their links.
    if (
        version != invoice.payment_link_version
        and invoice.status != Invoice.Status.PAID
    ):
        return None, Response(
            {"detail": REPLACED_LINK, "code": "link_replaced"},
            status=status.HTTP_410_GONE,
        )

    return invoice, None


class PublicInvoiceView(APIView):
    """
    What the customer sees when opening the link in the invoice email.
    No login: the signed token in the URL is the permission.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def get(self, request, token):
        invoice, problem = public_invoice_for(token)

        if problem:
            return problem

        return Response(
            {
                "invoice_number": invoice.invoice_number,
                "organization_name": invoice.organization.name,
                "status": invoice.status,
                "payable": payable_invoice_error(invoice) is None,
                "currency": invoice.currency,
                "issue_date": invoice.issue_date,
                "due_date": invoice.due_date,
                "subtotal": str(invoice.subtotal),
                "tax": str(invoice.tax),
                "total": str(invoice.total),
                "billing_email": invoice.billing_email,
                "items": [
                    {
                        "description": item.description,
                        "quantity": str(item.quantity),
                        "unit_price": str(item.unit_price),
                        "amount": str(item.amount),
                    }
                    for item in invoice.items.all()
                ],
            }
        )


class PublicInvoicePayView(APIView):
    """Start Stripe Checkout for the customer from the public link."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request, token):
        invoice, problem = public_invoice_for(token)

        if problem:
            return problem

        error = payable_invoice_error(invoice)

        if error:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page = f"{settings.FRONTEND_URL}/pay/{token}"

        try:
            checkout_session = create_invoice_checkout_session(
                invoice,
                success_url=f"{page}?paid=1",
                cancel_url=page,
            )
        except stripe.error.StripeError:
            return Response(
                {"detail": "Stripe could not create the payment session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"checkout_url": checkout_session.url},
            status=status.HTTP_201_CREATED,
        )


class PaymentListView(APIView):
    """
    Money received by the organization (Stripe and manual).
    Finance roles only.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationFinance,
    ]

    def get(self, request, organization_id):
        payments = (
            Payment.objects
            .filter(organization_id=organization_id)
            .select_related("invoice", "recorded_by")
        )

        return Response(
            PaymentSerializer(payments, many=True).data,
            status=status.HTTP_200_OK,
        )
