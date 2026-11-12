from django.urls import path

from .views import (
    InvoiceListCreateView,
    InvoiceDetailView,
    InvoicePDFView,
    InvoiceSendView,
    InvoicePaymentView,
    PaymentListView,
    PublicInvoicePayView,
    PublicInvoiceView,
)


urlpatterns = [
    # Customer payment link from the invoice email (no login).
    path(
        "public/<str:token>/",
        PublicInvoiceView.as_view(),
        name="public-invoice",
    ),
    path(
        "public/<str:token>/pay/",
        PublicInvoicePayView.as_view(),
        name="public-invoice-pay",
    ),
    path(
        "organizations/<uuid:organization_id>/payments/",
        PaymentListView.as_view(),
        name="payment-list",
    ),
    path(
        "organizations/<uuid:organization_id>/",
        InvoiceListCreateView.as_view(),
        name="invoice-list-create",
    ),
    path(
        "organizations/<uuid:organization_id>/<uuid:invoice_id>/",
        InvoiceDetailView.as_view(),
        name="invoice-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/<uuid:invoice_id>/pdf/",
        InvoicePDFView.as_view(),
        name="invoice-pdf",
    ),
    path(
        "organizations/<uuid:organization_id>/<uuid:invoice_id>/send/",
        InvoiceSendView.as_view(),
        name="invoice-send",
    ),
    path(
        "organizations/<uuid:organization_id>/<uuid:invoice_id>/pay/",
        InvoicePaymentView.as_view(),
        name="invoice-pay",
    ),
]