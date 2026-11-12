from decimal import Decimal

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

from weasyprint import HTML

from .models import Invoice
from .public import payment_link


PLATFORM_NAME = "SaaS Billing"

# Badge text -> colour class in the PDF template.
BADGE_CLASSES = {
    "PAID": "badge-green",
    "OPEN": "badge-blue",
    "OVERDUE": "badge-red",
    "PARTIALLY REFUNDED": "badge-amber",
    "REFUNDED": "badge-grey",
    "VOID": "badge-grey",
    "DRAFT": "badge-grey",
}


def build_invoice_pdf_context(invoice):
    """
    Everything the PDF shows, worked out here so the template stays
    dumb: who sells / who is billed, the status badge and the money
    actually paid and refunded.
    """

    organization = invoice.organization

    if invoice.stripe_invoice_id:
        # Platform subscription invoice: the platform bills the workspace.
        seller_name = PLATFORM_NAME
        seller_email = ""
        buyer_name = organization.name
    else:
        # Customer invoice: the workspace bills its customer.
        seller_name = organization.name
        seller_email = organization.billing_email or ""
        buyer_name = ""

    payments = list(invoice.payments.all())

    paid = sum((p.amount for p in payments), Decimal("0.00"))
    refunded = sum(
        (p.amount_refunded for p in payments), Decimal("0.00")
    )
    net_paid = paid - refunded

    paid_at = max((p.paid_at for p in payments), default=None)

    status = invoice.status

    if status == Invoice.Status.PAID and refunded > 0:
        badge = "REFUNDED" if net_paid <= 0 else "PARTIALLY REFUNDED"

    elif (
        status == Invoice.Status.OPEN
        and invoice.due_date
        and invoice.due_date < timezone.localdate()
    ):
        badge = "OVERDUE"

    else:
        badge = status

    if status in (Invoice.Status.OPEN, Invoice.Status.DRAFT):
        amount_due = invoice.total
    else:
        amount_due = Decimal("0.00")

    return {
        "invoice": invoice,
        "items": list(invoice.items.all()),
        "seller_name": seller_name,
        "seller_email": seller_email,
        "buyer_name": buyer_name,
        "buyer_email": invoice.billing_email,
        "badge": badge,
        "badge_class": BADGE_CLASSES.get(badge, "badge-grey"),
        "paid_at": paid_at,
        "paid": paid,
        "refunded": refunded,
        "net_paid": net_paid,
        "amount_due": amount_due,
        "is_void": status == Invoice.Status.VOID,
    }


def generate_invoice_pdf(invoice, request=None):
    html_string = render_to_string(
        "invoices/invoice_pdf.html",
        build_invoice_pdf_context(invoice),
    )

    base_url = None

    if request:
        base_url = request.build_absolute_uri("/")

    pdf = HTML(
        string=html_string,
        base_url=base_url,
    ).write_pdf()

    return pdf


def send_invoice_email(invoice, pdf):
    subject = f"Invoice {invoice.invoice_number}"

    body = (
        f"Dear Customer,\n\n"
        f"Please find attached invoice "
        f"{invoice.invoice_number}.\n\n"
        f"Amount Due: {invoice.total} {invoice.currency}\n"
        f"Due Date: {invoice.due_date}\n\n"
        f"Pay online by card:\n{payment_link(invoice)}\n\n"
        f"Thank you."
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=None,
        to=[invoice.billing_email],
    )

    email.attach(
        filename=f"{invoice.invoice_number}.pdf",
        content=pdf,
        mimetype="application/pdf",
    )

    email.send()

    return True


def send_dunning_reminder_email(invoice, attempt):
    subject = (
        f"Payment Reminder - Invoice {invoice.invoice_number}"
    )

    attempt_messages = {
        "FIRST_REMINDER": (
            "This is a reminder that your invoice is overdue."
        ),
        "SECOND_REMINDER": (
            "Your invoice remains overdue. "
            "Please arrange payment as soon as possible."
        ),
        "FINAL_REMINDER": (
            "This is a final payment reminder for your overdue invoice."
        ),
    }

    message = attempt_messages.get(
        attempt.attempt_type,
        "Your invoice is overdue. Please arrange payment.",
    )

    body = (
        f"Dear Customer,\n\n"
        f"{message}\n\n"
        f"Invoice: {invoice.invoice_number}\n"
        f"Amount Due: {invoice.total} {invoice.currency}\n"
        f"Due Date: {invoice.due_date}\n"
        f"Reminder Number: {attempt.attempt_number}\n\n"
        f"Please make the payment at your earliest convenience:\n"
        f"{payment_link(invoice)}\n\n"
        f"Thank you."
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=None,
        to=[invoice.billing_email],
    )

    email.send()

    return True