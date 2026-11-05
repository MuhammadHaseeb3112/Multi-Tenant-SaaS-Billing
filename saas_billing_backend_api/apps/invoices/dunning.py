from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import DunningAttempt, Invoice


DUNNING_SCHEDULE = (
    (
        1,
        DunningAttempt.AttemptType.FIRST_REMINDER,
    ),
    (
        3,
        DunningAttempt.AttemptType.SECOND_REMINDER,
    ),
    (
        7,
        DunningAttempt.AttemptType.FINAL_REMINDER,
    ),
)


def get_due_dunning_attempt(invoice, today=None):
    """
    Determine which dunning attempt is currently due
    for an overdue invoice.

    Returns:
        tuple[int, str] | None
    """

    if invoice.status != Invoice.Status.OPEN:
        return None

    if invoice.due_date is None:
        return None

    today = today or timezone.localdate()

    days_overdue = (today - invoice.due_date).days

    if days_overdue < 1:
        return None

    due_attempt = None

    for days_after_due, attempt_type in DUNNING_SCHEDULE:
        if days_overdue >= days_after_due:
            due_attempt = (
                days_after_due,
                attempt_type,
            )

    if due_attempt is None:
        return None

    attempt_number = DUNNING_SCHEDULE.index(
        due_attempt
    ) + 1

    return (
        attempt_number,
        due_attempt[1],
    )


def create_dunning_attempt(
    invoice,
    today=None,
):
    """
    Create the next dunning attempt if one is due.

    Returns:
        DunningAttempt | None
    """

    today = today or timezone.localdate()

    due_attempt = get_due_dunning_attempt(
        invoice=invoice,
        today=today,
    )

    if due_attempt is None:
        return None

    attempt_number, attempt_type = due_attempt

    existing_attempt = (
        DunningAttempt.objects.filter(
            invoice=invoice,
            attempt_number=attempt_number,
        )
        .first()
    )

    if existing_attempt:
        return existing_attempt

    scheduled_at = timezone.make_aware(
        timezone.datetime.combine(
            today,
            timezone.datetime.min.time(),
        )
    )

    try:
        with transaction.atomic():
            return DunningAttempt.objects.create(
                invoice=invoice,
                organization=invoice.organization,
                attempt_type=attempt_type,
                attempt_number=attempt_number,
                status=DunningAttempt.Status.PENDING,
                scheduled_at=scheduled_at,
            )
    except IntegrityError:
        return (
            DunningAttempt.objects.filter(
                invoice=invoice,
                attempt_number=attempt_number,
            )
            .first()
        )


def process_overdue_invoice(
    invoice,
    today=None,
):
    """
    Determine and create the next dunning attempt
    for one invoice.
    """

    return create_dunning_attempt(
        invoice=invoice,
        today=today,
    )


def process_overdue_invoices(today=None):
    """
    Find overdue OPEN invoices and create any
    dunning attempts that are currently due.

    Returns the number of newly created attempts.
    """

    today = today or timezone.localdate()

    invoices = (
        Invoice.objects
        .select_related("organization")
        .filter(
            status=Invoice.Status.OPEN,
            due_date__isnull=False,
            due_date__lt=today,
        )
    )

    created_count = 0

    for invoice in invoices:
        existing_attempt_count = (
            DunningAttempt.objects
            .filter(invoice=invoice)
            .count()
        )

        attempt = process_overdue_invoice(
            invoice=invoice,
            today=today,
        )

        if (
            attempt is not None
            and existing_attempt_count
            < attempt.attempt_number
        ):
            created_count += 1

    return created_count