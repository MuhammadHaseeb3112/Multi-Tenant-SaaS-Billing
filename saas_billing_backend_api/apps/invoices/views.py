import stripe

from django.conf import settings
from django.db import transaction
from .tasks import send_invoice_email_task
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
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

from .models import Invoice, Payment
from .payments import record_manual_payment
from .serializers import InvoiceSerializer, PaymentSerializer


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

    def post(self, request, organization_id):
        serializer = InvoiceSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        organization = get_object_or_404(
            Organization,
            id=organization_id,
        )

        invoice = serializer.save(
            organization=organization,
        )

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
            Invoice.objects.prefetch_related("items"),
            id=invoice_id,
            organization_id=organization_id,
        )

        if invoice.status != Invoice.Status.DRAFT:
            return Response(
                {
                    "detail": "Only draft invoices can be sent."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not invoice.billing_email:
            return Response(
                {
                    "detail": "Invoice billing email is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice.status = Invoice.Status.OPEN

        invoice.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        transaction.on_commit(
            lambda: send_invoice_email_task.delay(
                str(invoice.id)
            )
        )

        return Response(
            {
                "detail": "Invoice queued for email delivery.",
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "billing_email": invoice.billing_email,
            },
            status=status.HTTP_202_ACCEPTED,
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

        # Already paid
        if invoice.status == Invoice.Status.PAID:
            return Response(
                {"detail": "This invoice has already been paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only OPEN invoices can be paid
        if invoice.status != Invoice.Status.OPEN:
            return Response(
                {"detail": "Only open invoices can be paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Current Stripe Checkout implementation supports USD only
        if invoice.currency != Invoice.Currency.USD:
            return Response(
                {
                    "detail": (
                        "Stripe payment is currently available only "
                        "for USD invoices."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = int(invoice.total * 100)

        if amount <= 0:
            return Response(
                {"detail": "Invoice total must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            checkout_session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": invoice.currency.lower(),
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                            },
                            "unit_amount": amount,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
                customer_email=invoice.billing_email,
                metadata={
                    "invoice_id": str(invoice.id),
                    "organization_id": str(invoice.organization_id),
                    "invoice_number": invoice.invoice_number,
                    "payment_type": "invoice",
                },
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
