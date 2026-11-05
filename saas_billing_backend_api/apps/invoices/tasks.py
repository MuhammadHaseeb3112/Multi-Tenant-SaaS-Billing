from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from .models import DunningAttempt, Invoice
from .services import (
    generate_invoice_pdf,
    send_dunning_reminder_email,
    send_invoice_email,
)


User = get_user_model()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_invoice_email_task(self, invoice_id):

    invoice = (
        Invoice.objects
        .prefetch_related("items")
        .get(id=invoice_id)
    )

    pdf = generate_invoice_pdf(
        invoice=invoice,
    )

    send_invoice_email(
        invoice=invoice,
        pdf=pdf,
    )

    return {
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "status": "sent",
    }


@shared_task
def create_due_dunning_attempts():
    """
    Find overdue OPEN invoices and create any dunning attempts that
    are due today (day 1, 3 and 7 after the due date).

    Runs on a schedule BEFORE process_dunning_attempts, which sends the
    reminders. Safe to run repeatedly: existing attempts are reused.
    """

    from .dunning import process_overdue_invoices

    return process_overdue_invoices()


@shared_task
def process_dunning_attempts():
    """
    Process all pending dunning attempts whose scheduled time
    has arrived.
    """

    now = timezone.now()

    attempts = (
        DunningAttempt.objects
        .select_related(
            "invoice",
            "organization",
        )
        .filter(
            status=DunningAttempt.Status.PENDING,
            scheduled_at__lte=now,
        )
        .order_by("scheduled_at", "attempt_number")
    )

    processed_count = 0
    failed_count = 0

    for attempt in attempts:

        invoice = attempt.invoice

        # Do not send a reminder for an invoice that has
        # already been paid, voided, or otherwise closed.
        if invoice.status != Invoice.Status.OPEN:
            attempt.status = DunningAttempt.Status.FAILED
            attempt.failed_at = now
            attempt.error_message = (
                "Invoice is no longer open."
            )
            attempt.save(
                update_fields=[
                    "status",
                    "failed_at",
                    "error_message",
                    "updated_at",
                ]
            )
            continue

        try:
            send_dunning_reminder_email(
                invoice=invoice,
                attempt=attempt,
            )

            attempt.status = DunningAttempt.Status.SENT
            attempt.sent_at = timezone.now()
            attempt.error_message = ""
            attempt.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "error_message",
                    "updated_at",
                ]
            )

            # Send the in-app notification only to the active
            # organization member whose email matches the
            # invoice billing email.
            user = (
                User.objects
                .filter(
                    email__iexact=invoice.billing_email,
                    memberships__organization=invoice.organization,
                    memberships__is_active=True,
                    is_active=True,
                )
                .distinct()
                .first()
            )

            if user:
                notification_titles = {
                    DunningAttempt.AttemptType.FIRST_REMINDER:
                        "Invoice Overdue",
                    DunningAttempt.AttemptType.SECOND_REMINDER:
                        "Second Payment Reminder",
                    DunningAttempt.AttemptType.FINAL_REMINDER:
                        "Final Payment Reminder",
                }

                title = notification_titles.get(
                    attempt.attempt_type,
                    "Invoice Overdue",
                )

                create_notification(
                    organization=invoice.organization,
                    user=user,
                    notification_type=(
                        Notification.NotificationType.INVOICE_OVERDUE
                    ),
                    title=title,
                    message=(
                        f"Invoice {invoice.invoice_number} "
                        f"is overdue. Amount due: "
                        f"{invoice.total} {invoice.currency}."
                    ),
                )

            processed_count += 1

        except Exception as exc:
            attempt.status = DunningAttempt.Status.FAILED
            attempt.failed_at = timezone.now()
            attempt.error_message = str(exc)[:1000]

            attempt.save(
                update_fields=[
                    "status",
                    "failed_at",
                    "error_message",
                    "updated_at",
                ]
            )

            failed_count += 1

    return {
        "processed": processed_count,
        "failed": failed_count,
    }