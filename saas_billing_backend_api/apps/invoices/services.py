from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from weasyprint import HTML

from .models import Invoice


def generate_invoice_pdf(invoice, request=None):
    html_string = render_to_string(
        "invoices/invoice_pdf.html",
        {
            "invoice": invoice,
        },
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
        f"Please make the payment at your earliest convenience.\n\n"
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