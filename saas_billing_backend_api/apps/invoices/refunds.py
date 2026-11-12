"""
Refunds and credit notes from Stripe.

Refund events (refund.created / refund.updated, and charge.refunded as a
fallback) create or update one Refund row per Stripe refund. The payment
they belong to is found by PaymentIntent:

  1. Payment.stripe_payment_intent_id (invoice Checkout payments), else
  2. Stripe InvoicePayment lookup PaymentIntent -> invoice ->
     Payment.stripe_invoice_id (subscription invoices; since API
     2025-03-31 the invoice no longer carries its payment_intent).

After every change Payment.amount_refunded and its status are recomputed
from the SUCCEEDED refunds, so replays and out-of-order events
(updated before created, pending -> succeeded) always converge.
"""

import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import CreditNote, Invoice, Payment, Refund
from .payments import cents_to_decimal, timestamp_to_datetime


logger = logging.getLogger(__name__)


REFUND_STATUS = {
    "pending": Refund.Status.PENDING,
    "requires_action": Refund.Status.PENDING,
    "succeeded": Refund.Status.SUCCEEDED,
    "failed": Refund.Status.FAILED,
    "canceled": Refund.Status.CANCELED,
}


def _stripe_id(value):
    if isinstance(value, dict):
        return value.get("id")
    return value or None


# =============================================================================
# Payment lookup
# =============================================================================

def find_payment_for_payment_intent(payment_intent_id):
    if not payment_intent_id:
        return None

    payment = Payment.objects.filter(
        stripe_payment_intent_id=payment_intent_id
    ).first()

    if payment:
        return payment

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # stripe-python 15: API objects are not dicts (.get() raises), so
    # convert the result before reading it.
    invoice_payments = stripe.InvoicePayment.list(
        payment={
            "type": "payment_intent",
            "payment_intent": payment_intent_id,
        },
        limit=1,
    ).to_dict()

    for invoice_payment in invoice_payments.get("data", []):
        stripe_invoice_id = _stripe_id(invoice_payment.get("invoice"))

        payment = Payment.objects.filter(
            stripe_invoice_id=stripe_invoice_id
        ).first()

        if payment:
            # Remember it so later refunds need no Stripe call.
            payment.stripe_payment_intent_id = payment_intent_id
            payment.save(update_fields=["stripe_payment_intent_id"])
            return payment

    return None


# =============================================================================
# Refunds
# =============================================================================

def recalculate_refunds(payment):
    """
    amount_refunded = sum of SUCCEEDED refunds (capped at the amount);
    status SUCCEEDED / PARTIALLY_REFUNDED / REFUNDED accordingly.
    """

    refunded = (
        payment.refunds
        .filter(status=Refund.Status.SUCCEEDED)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    refunded = min(refunded, payment.amount)

    if refunded <= 0:
        status = Payment.Status.SUCCEEDED
    elif refunded >= payment.amount:
        status = Payment.Status.REFUNDED
    else:
        status = Payment.Status.PARTIALLY_REFUNDED

    payment.amount_refunded = refunded
    payment.status = status
    payment.save(update_fields=["amount_refunded", "status"])

    return payment


def sync_stripe_refund(stripe_refund):
    """
    Create or update the Refund for a Stripe refund object. Idempotent.
    Returns the Refund.
    """

    refund_id = stripe_refund.get("id")

    if not refund_id:
        raise ValueError("Stripe refund is missing its ID.")

    payment_intent_id = _stripe_id(stripe_refund.get("payment_intent"))
    charge_id = _stripe_id(stripe_refund.get("charge"))

    with transaction.atomic():
        refund = (
            Refund.objects
            .select_for_update()
            .filter(stripe_refund_id=refund_id)
            .first()
        )

        payment = refund.payment if refund else None

        if payment is None:
            payment = find_payment_for_payment_intent(payment_intent_id)

        if payment is not None:
            # Lock the payment so two refunds of it can't race on the
            # amount_refunded recalculation.
            payment = Payment.objects.select_for_update().get(
                pk=payment.pk
            )
        else:
            logger.warning(
                "Stripe refund %s (payment_intent=%s) matches no local "
                "payment; stored without a payment.",
                refund_id,
                payment_intent_id,
            )

        values = {
            "organization_id": payment.organization_id if payment else None,
            "payment": payment,
            "stripe_payment_intent_id": payment_intent_id or "",
            "stripe_charge_id": charge_id or "",
            "amount": cents_to_decimal(stripe_refund.get("amount")),
            "currency": (stripe_refund.get("currency") or "usd").upper(),
            "status": REFUND_STATUS.get(
                stripe_refund.get("status"), Refund.Status.PENDING
            ),
            "reason": stripe_refund.get("reason") or "",
            "refunded_at": (
                timestamp_to_datetime(stripe_refund.get("created"))
                or timezone.now()
            ),
        }

        refund, _ = Refund.objects.update_or_create(
            stripe_refund_id=refund_id,
            defaults=values,
        )

        if payment is not None:
            recalculate_refunds(payment)

    return refund


def sync_refunds_for_charge(stripe_charge):
    """
    charge.refunded: the charge object no longer embeds its refunds, so
    list them from Stripe and sync each one.
    """

    charge_id = stripe_charge.get("id")

    if not charge_id:
        raise ValueError("Stripe charge is missing its ID.")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    refunds = stripe.Refund.list(charge=charge_id, limit=100)

    # stripe-python 15: Refund objects are not dicts, and
    # sync_stripe_refund reads them with .get() (as it does the plain
    # dicts that arrive in refund.* webhooks), so convert each one.
    return [
        sync_stripe_refund(stripe_refund.to_dict())
        for stripe_refund in refunds.auto_paging_iter()
    ]


# =============================================================================
# Credit notes
# =============================================================================

def sync_stripe_credit_note(stripe_credit_note, organization):
    """
    Create or update the local CreditNote mirror. Idempotent.
    """

    credit_note_id = stripe_credit_note.get("id")

    if not credit_note_id:
        raise ValueError("Stripe credit note is missing its ID.")

    stripe_invoice_id = _stripe_id(stripe_credit_note.get("invoice")) or ""

    credit_note, _ = CreditNote.objects.update_or_create(
        stripe_credit_note_id=credit_note_id,
        defaults={
            "organization": organization,
            "invoice": Invoice.objects.filter(
                organization=organization,
                stripe_invoice_id=stripe_invoice_id,
            ).first() if stripe_invoice_id else None,
            "stripe_invoice_id": stripe_invoice_id,
            "number": stripe_credit_note.get("number") or "",
            "amount": cents_to_decimal(stripe_credit_note.get("total")),
            "currency": (
                stripe_credit_note.get("currency") or "usd"
            ).upper(),
            "reason": stripe_credit_note.get("reason") or "",
            "status": (
                CreditNote.Status.VOID
                if stripe_credit_note.get("status") == "void"
                else CreditNote.Status.ISSUED
            ),
            "issued_at": (
                timestamp_to_datetime(stripe_credit_note.get("created"))
                or timezone.now()
            ),
        },
    )

    return credit_note
