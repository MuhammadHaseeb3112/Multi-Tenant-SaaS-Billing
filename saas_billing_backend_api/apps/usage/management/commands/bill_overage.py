"""
Manually bill usage overage for a closed period, e.g. when the
``invoice.created`` webhook was missed.

The charge is created as a pending Stripe invoice item on the
subscription, so Stripe adds it to the NEXT invoice. Idempotent: a
period that was already billed is skipped.

    python manage.py bill_overage --organization <uuid> \
        --start 2026-10-01T00:00:00Z --end 2026-11-01T00:00:00Z --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.billing.models import Subscription
from apps.usage.models import OverageCharge
from apps.usage.overage import bill_overage, calculate_period_overage


class Command(BaseCommand):
    help = "Bill API usage overage for one closed billing period."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--start", required=True)
        parser.add_argument("--end", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        start = parse_datetime(options["start"])
        end = parse_datetime(options["end"])

        if not start or not end or start.tzinfo is None or end.tzinfo is None:
            raise CommandError(
                "--start/--end must be ISO datetimes with a timezone, "
                "e.g. 2026-10-01T00:00:00Z"
            )

        if start >= end:
            raise CommandError("--start must be before --end.")

        subscription = (
            Subscription.objects
            .select_related("plan", "organization")
            .filter(organization_id=options["organization"])
            .first()
        )

        if subscription is None:
            raise CommandError("Organization has no subscription.")

        if OverageCharge.objects.filter(
            subscription=subscription, period_start=start
        ).exists():
            self.stdout.write("Already billed for this period. Nothing to do.")
            return

        used, included, overage, price, amount = calculate_period_overage(
            subscription, start, end
        )

        self.stdout.write(
            f"{subscription.organization.name}: used {used}, included "
            f"{included}, overage {overage} x {price}/1000 = {amount}"
        )

        if options["dry_run"] or amount <= 0:
            self.stdout.write("Nothing billed.")
            return

        charge = bill_overage(
            subscription=subscription,
            period_start=start,
            period_end=end,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created pending invoice item "
                f"{charge.stripe_invoice_item_id} ({charge.amount})."
            )
        )
