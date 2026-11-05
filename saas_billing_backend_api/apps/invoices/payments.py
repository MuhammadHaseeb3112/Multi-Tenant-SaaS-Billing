"""
Recording money that was actually received.

All Payment rows are created here so the rules live in one place:

- mirror_paid_stripe_invoice: a Stripe subscription invoice was paid.
  Creates/updates a local Invoice (with items) and one Payment.
- record_invoice_checkout_payment: a local invoice was paid through
  Stripe Checkout.
- record_manual_payment: a finance user marked an invoice PAID by hand.

Stripe-based functions are idempotent: the unique Stripe IDs on Invoice
and Payment mean a replayed webhook never records money twice.
"""

from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceItem, Payment


TWO_PLACES = Decimal("0.01")


def cents_to_decimal(value):
    """Stripe amounts are integers in the smallest currency unit."""

    return (
        Decimal(value or 0) / Decimal(100)
    ).quantize(TWO_PLACES)


def timestamp_to_datetime(value):
    if not value:
        return None

    return datetime.fromtimestamp(value, tz=datetime_timezone.utc)


def _invoice_paid_at(stripe_invoice):
    transitions = stripe_invoice.get("status_transitions") or {}

    return (
        timestamp_to_datetime(transitions.get("paid_at"))
        or timestamp_to_datetime(stripe_invoice.get("created"))
        or timezone.now()
    )


def _invoice_amounts(stripe_invoice):
    """
    Return (subtotal, tax, total) so that subtotal + tax == total,
    matching how local invoices are stored.
    """

    total = cents_to_decimal(stripe_invoice.get("total"))

    tax = sum(
        (
            cents_to_decimal(entry.get("amount"))
            for entry in stripe_invoice.get("total_taxes") or []
        ),
        Decimal("0.00"),
    )

    return total - tax, tax, total


def _create_items(invoice, stripe_invoice):
    lines = (stripe_invoice.get("lines") or {}).get("data") or []

    for line in lines:
        amount = cents_to_decimal(line.get("amount"))
        quantity = Decimal(line.get("quantity") or 1)

        unit_price = (amount / quantity).quantize(TWO_PLACES)

        # InvoiceItem recalculates amount = quantity * unit_price.
        # If the division is not exact, store one unit at the full
        # amount so the item total always matches Stripe.
        if unit_price * quantity != amount:
            quantity = Decimal("1")
            unit_price = amount

        InvoiceItem.objects.create(
            invoice=invoice,
            description=(
                line.get("description") or "Subscription"
            )[:255],
            quantity=quantity,
            unit_price=unit_price,
        )


@transaction.atomic
def mirror_paid_stripe_invoice(stripe_invoice, organization):
    """
    Make sure a paid Stripe invoice exists locally as a PAID Invoice
    with one Payment. Returns (invoice, payment). ``payment`` is None
    for zero-amount invoices (e.g. trials).
    """

    stripe_invoice_id = stripe_invoice.get("id")

    if not stripe_invoice_id:
        raise ValueError("Stripe invoice is missing an ID.")

    subtotal, tax, total = _invoice_amounts(stripe_invoice)
    paid_at = _invoice_paid_at(stripe_invoice)

    invoice = (
        Invoice.objects
        .select_for_update()
        .filter(stripe_invoice_id=stripe_invoice_id)
        .first()
    )

    if invoice is None:
        created_at = (
            timestamp_to_datetime(stripe_invoice.get("created"))
            or paid_at
        )
        due_date = timestamp_to_datetime(
            stripe_invoice.get("due_date")
        )

        invoice = Invoice.objects.create(
            organization=organization,
            invoice_number=(
                stripe_invoice.get("number")
                or f"STRIPE-{stripe_invoice_id[-8:]}"
            ),
            status=Invoice.Status.PAID,
            issue_date=created_at.date(),
            due_date=due_date.date() if due_date else None,
            currency=(
                stripe_invoice.get("currency") or "usd"
            ).upper(),
            subtotal=subtotal,
            tax=tax,
            total=total,
            billing_email=(
                stripe_invoice.get("customer_email")
                or organization.billing_email
            ),
            stripe_invoice_id=stripe_invoice_id,
        )

        _create_items(invoice, stripe_invoice)

    else:
        if invoice.organization_id != organization.id:
            raise ValueError(
                f"Stripe invoice {stripe_invoice_id} is already "
                f"linked to a different organization."
            )

        if invoice.status != Invoice.Status.PAID:
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=["status", "updated_at"])

    amount_paid = cents_to_decimal(stripe_invoice.get("amount_paid"))

    if amount_paid <= 0:
        return invoice, None

    payment, _ = Payment.objects.get_or_create(
        stripe_invoice_id=stripe_invoice_id,
        defaults={
            "organization": organization,
            "invoice": invoice,
            "amount": amount_paid,
            "currency": invoice.currency,
            "method": Payment.Method.STRIPE,
            "description": f"Stripe invoice {invoice.invoice_number}",
            "paid_at": paid_at,
        },
    )

    return invoice, payment


def record_invoice_checkout_payment(session, invoice):
    """
    Record the Payment for a local invoice paid via Stripe Checkout.
    Idempotent on the Checkout Session ID.
    """

    payment, _ = Payment.objects.get_or_create(
        stripe_checkout_session_id=session.get("id"),
        defaults={
            "organization": invoice.organization,
            "invoice": invoice,
            "amount": cents_to_decimal(session.get("amount_total")),
            "currency": (
                session.get("currency") or invoice.currency
            ).upper(),
            "method": Payment.Method.STRIPE,
            "stripe_payment_intent_id": session.get("payment_intent"),
            "description": (
                f"Stripe Checkout for invoice {invoice.invoice_number}"
            ),
            "paid_at": timezone.now(),
        },
    )

    return payment


def record_manual_payment(invoice, user):
    """Money received outside Stripe (bank transfer, cash, ...)."""

    return Payment.objects.create(
        organization=invoice.organization,
        invoice=invoice,
        amount=invoice.total,
        currency=invoice.currency,
        method=Payment.Method.MANUAL,
        recorded_by=user,
        description=f"Manually marked paid: {invoice.invoice_number}",
        paid_at=timezone.now(),
    )
