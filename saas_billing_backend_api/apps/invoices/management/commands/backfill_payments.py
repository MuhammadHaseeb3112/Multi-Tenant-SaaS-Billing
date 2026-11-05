"""
Bring payments made BEFORE the Payment model existed into the database.

Two sources:

1. Stripe: every PAID Stripe invoice is mirrored exactly like the
   invoice.paid webhook does (local Invoice + STRIPE Payment).
2. Local: invoices already marked PAID locally (no Stripe invoice) that
   have no Payment get one MANUAL Payment dated at their last update.

Safe to run many times: existing rows are detected and skipped.
Always try --dry-run first.

    python manage.py backfill_payments --dry-run
    python manage.py backfill_payments
    python manage.py backfill_payments --skip-stripe
"""

import stripe

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.invoices.models import Invoice, Payment
from apps.invoices.payments import mirror_paid_stripe_invoice


class Command(BaseCommand):
    help = (
        "Create Payment records for invoices paid before payments "
        "were tracked. Idempotent; use --dry-run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be created.",
        )
        parser.add_argument(
            "--skip-stripe",
            action="store_true",
            help="Do not call Stripe; only backfill local PAID invoices.",
        )
        parser.add_argument(
            "--skip-local",
            action="store_true",
            help="Only backfill from Stripe.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write("DRY RUN - nothing will be saved.")

        if not options["skip_stripe"]:
            self.backfill_stripe(dry_run)

        if not options["skip_local"]:
            self.backfill_local(dry_run)

    # -----------------------------------------------------------------
    # Stripe invoices
    # -----------------------------------------------------------------

    def backfill_stripe(self, dry_run):
        # Imported here to reuse the exact organization lookup the
        # webhook uses (local subscription, then Stripe metadata).
        from apps.webhooks.views import StripeWebhookView

        webhook = StripeWebhookView()

        stripe.api_key = settings.STRIPE_SECRET_KEY

        created = already = no_org = 0

        invoices = stripe.Invoice.list(status="paid", limit=100)

        for stripe_invoice in invoices.auto_paging_iter():
            data = stripe_invoice.to_dict()
            stripe_invoice_id = data.get("id")

            organization = webhook.get_invoice_organization(data)

            if organization is None:
                no_org += 1
                self.stdout.write(
                    f"  skip {stripe_invoice_id}: organization not found"
                )
                continue

            exists = Invoice.objects.filter(
                stripe_invoice_id=stripe_invoice_id
            ).exists() and (
                Payment.objects.filter(
                    stripe_invoice_id=stripe_invoice_id
                ).exists()
                or not data.get("amount_paid")
            )

            if exists:
                already += 1
                continue

            created += 1

            if dry_run:
                self.stdout.write(
                    f"  would import {stripe_invoice_id} for "
                    f"{organization.name}"
                )
                continue

            mirror_paid_stripe_invoice(data, organization)

        self.stdout.write(
            self.style.SUCCESS(
                f"Stripe: {created} imported"
                f"{' (dry run)' if dry_run else ''}, "
                f"{already} already present, "
                f"{no_org} skipped (no organization)."
            )
        )

    # -----------------------------------------------------------------
    # Local PAID invoices without a Payment
    # -----------------------------------------------------------------

    def backfill_local(self, dry_run):
        invoices = (
            Invoice.objects
            .filter(
                status=Invoice.Status.PAID,
                stripe_invoice_id__isnull=True,
                payments__isnull=True,
            )
            .select_related("organization")
        )

        count = 0

        for invoice in invoices:
            count += 1

            if dry_run:
                self.stdout.write(
                    f"  would record {invoice.total} {invoice.currency} "
                    f"for {invoice.invoice_number} "
                    f"({invoice.organization.name})"
                )
                continue

            with transaction.atomic():
                Payment.objects.create(
                    organization=invoice.organization,
                    invoice=invoice,
                    amount=invoice.total,
                    currency=invoice.currency,
                    method=Payment.Method.MANUAL,
                    description=(
                        f"Backfilled: {invoice.invoice_number} was "
                        f"marked PAID before payments were tracked"
                    ),
                    # Best available date for when it was paid.
                    paid_at=invoice.updated_at,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Local: {count} PAID invoice(s) "
                f"{'would get' if dry_run else 'got'} a MANUAL payment."
            )
        )
