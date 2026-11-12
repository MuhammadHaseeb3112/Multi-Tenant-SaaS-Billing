"""
Create (or reset) realistic demo data for the public live demo.

    python manage.py seed_demo            # create if missing
    python manage.py seed_demo --reset    # delete demo data, recreate

Demo logins (password from DEMO_PASSWORD, default "DemoPass123!"):
    owner@demo.com       OWNER of "Acme Analytics" (PRO) and "Beta Labs" (FREE)
    accountant@demo.com  ACCOUNTANT of Acme
    member@demo.com      MEMBER of Acme

Only touches organizations with the demo slugs and users with @demo.com
emails, so it is safe to run against a database with real data.
"""

import os
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.billing.models import Plan, Subscription
from apps.invoices.models import Invoice, InvoiceItem, Payment, Refund
from apps.notifications.models import Notification
from apps.tenants.models import Membership, Organization
from apps.usage.models import ApiKey, OverageCharge, UsageRecord


DEMO_DOMAIN = "@demo.com"
DEMO_SLUGS = ("acme-analytics-demo", "beta-labs-demo")

PLANS = [
    # code, name, description, monthly, annual, limit, overage/1000, cap
    ("FREE", "Free", "For trying things out", "0.00", "0.00", 1000, "0.00", None),
    ("PRO", "Pro", "For growing teams", "29.00", "290.00", 10000, "2.00", 50000),
    ("ENTERPRISE", "Enterprise", "For scale", "99.00", "990.00", 100000, "1.00", 500000),
]

STRIPE = Payment.Method.STRIPE
MANUAL = Payment.Method.MANUAL

# Paid customer invoices:
# months ago, extra days, number, client, work, total, paid by
CUSTOMER_INVOICES = [
    (5, 6, "INV-1030", "finance@northwind.example", "Dashboard build", "640.00", STRIPE),
    (4, 12, "INV-1031", "ap@globex.example", "Data pipeline setup", "1200.00", MANUAL),
    (4, 3, "INV-1032", "billing@initech.example", "Monthly reporting", "380.00", STRIPE),
    (3, 8, "INV-1033", "finance@northwind.example", "Analytics consulting", "950.00", STRIPE),
    (2, 14, "INV-1034", "ap@globex.example", "Custom integration", "1500.00", MANUAL),
    (2, 4, "INV-1035", "billing@initech.example", "Monthly reporting", "420.00", STRIPE),
    (1, 9, "INV-1036", "finance@northwind.example", "Forecast model", "900.00", STRIPE),
    (1, 2, "INV-1037", "ap@globex.example", "Team training", "1750.00", MANUAL),
    (0, 3, "INV-1038", "billing@initech.example", "Monthly reporting", "1100.00", STRIPE),
]

REFUNDED_INVOICE = "INV-1036"

class Command(BaseCommand):
    help = "Create realistic demo organizations, users and billing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)  # same demo every time

        if options["reset"]:
            self.reset()
        elif Organization.objects.filter(slug=DEMO_SLUGS[0]).exists():
            self.stdout.write("Demo data already exists (use --reset).")
            return

        plans = self.create_plans()
        password = os.environ.get("DEMO_PASSWORD", "DemoPass123!")

        owner = self.user("owner@demo.com", "Sarah", "Khan", password)
        accountant = self.user("accountant@demo.com", "Ali", "Raza", password)
        member = self.user("member@demo.com", "Omar", "Sheikh", password)

        acme = Organization.objects.create(
            name="Acme Analytics",
            slug=DEMO_SLUGS[0],
            billing_email="billing@acme.example",
        )
        beta = Organization.objects.create(
            name="Beta Labs",
            slug=DEMO_SLUGS[1],
            billing_email="billing@beta.example",
        )

        for user, role in (
            (owner, Membership.Role.OWNER),
            (accountant, Membership.Role.ACCOUNTANT),
            (member, Membership.Role.MEMBER),
        ):
            Membership.objects.create(user=user, organization=acme, role=role)
        Membership.objects.create(
            user=owner, organization=beta, role=Membership.Role.OWNER
        )

        now = timezone.now()
        period_start = now - timedelta(days=12)

        acme_sub = Subscription.objects.create(
            organization=acme,
            plan=plans["PRO"],
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
            current_period_start=period_start,
            current_period_end=period_start + timedelta(days=30),
        )
        Subscription.objects.create(
            organization=beta,
            plan=plans["FREE"],
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
        )

        self.create_billing_history(acme, acme_sub, owner, now)
        self.create_usage(acme, owner, period_start, now)
        self.create_activity(acme, owner, accountant, member)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo ready. Log in as owner@demo.com, accountant@demo.com "
                "or member@demo.com."
            )
        )

    # ------------------------------------------------------------------

    def reset(self):
        Organization.objects.filter(slug__in=DEMO_SLUGS).delete()
        User.objects.filter(email__endswith=DEMO_DOMAIN).delete()
        self.stdout.write("Removed previous demo data.")

    def create_plans(self):
        plans = {}

        for code, name, desc, monthly, annual, limit, overage, cap in PLANS:
            plan, _ = Plan.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": desc,
                    "monthly_price": Decimal(monthly),
                    "annual_price": Decimal(annual),
                    "api_request_limit": limit,
                    "overage_price_per_1000": Decimal(overage),
                    "max_overage_requests": cap,
                    # Stripe test price IDs, if configured for checkout.
                    "stripe_monthly_price_id": os.environ.get(
                        f"DEMO_STRIPE_{code}_MONTHLY_PRICE"
                    ) or None,
                    "stripe_annual_price_id": os.environ.get(
                        f"DEMO_STRIPE_{code}_ANNUAL_PRICE"
                    ) or None,
                },
            )
            plans[code] = plan

        return plans

    def user(self, email, first, last, password):
        return User.objects.create_user(
            email=email,
            password=password,
            first_name=first,
            last_name=last,
        )

    def create_billing_history(self, org, subscription, owner, now):
        # Six monthly PRO subscription payments to the platform (oldest
        # first), paid customer invoices spread over the same months,
        # plus customer invoices still open, overdue and in draft.
        for months_ago in range(5, -1, -1):
            paid_at = now - timedelta(days=30 * months_ago + 2)
            number = f"DEMO-{paid_at:%Y%m}"
            invoice = Invoice.objects.create(
                organization=org,
                invoice_number=number,
                status=Invoice.Status.PAID,
                issue_date=paid_at.date(),
                due_date=paid_at.date(),
                currency="USD",
                subtotal=Decimal("29.00"),
                tax=Decimal("0.00"),
                total=Decimal("29.00"),
                billing_email=org.billing_email,
                # Marks it as a platform subscription invoice (shown
                # under "Platform billing", not as customer revenue).
                stripe_invoice_id=f"in_demo_{number}",
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                description="Pro plan (monthly)",
                quantity=Decimal("1"),
                unit_price=Decimal("29.00"),
                amount=Decimal("29.00"),
            )
            Payment.objects.create(
                organization=org,
                invoice=invoice,
                amount=Decimal("29.00"),
                currency="USD",
                method=Payment.Method.STRIPE,
                stripe_invoice_id=f"in_demo_{number}",
                paid_at=paid_at,
            )

        # Last period went over the limit: overage on the renewal invoice.
        OverageCharge.objects.create(
            organization=org,
            subscription=subscription,
            period_start=now - timedelta(days=42),
            period_end=now - timedelta(days=12),
            included_requests=10000,
            used_requests=12350,
            overage_requests=2350,
            price_per_1000=Decimal("2.00"),
            amount=Decimal("4.70"),
            status=OverageCharge.Status.BILLED,
            stripe_invoice_id="in_demo_overage",
            stripe_invoice_item_id="ii_demo_overage",
        )

        self.create_customer_payments(org, owner, now)

        today = date.today()
        for number, status, total, due in (
            ("INV-1042", Invoice.Status.OPEN, "480.00", today + timedelta(days=14)),
            ("INV-1043", Invoice.Status.DRAFT, "1250.00", today + timedelta(days=30)),
            ("INV-1039", Invoice.Status.OPEN, "320.00", today - timedelta(days=9)),
        ):
            invoice = Invoice.objects.create(
                organization=org,
                invoice_number=number,
                status=status,
                issue_date=today - timedelta(days=5),
                due_date=due,
                currency="USD",
                subtotal=Decimal(total),
                tax=Decimal("0.00"),
                total=Decimal(total),
                billing_email="accounts@client.example",
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                description="Consulting services",
                quantity=Decimal("1"),
                unit_price=Decimal(total),
                amount=Decimal(total),
            )

    def create_customer_payments(self, org, owner, now):
        """
        Paid customer invoices over the last six months, so revenue
        charts and "Collected from Customers" have something to show.
        One Stripe payment is partially refunded.
        """

        for months_ago, days, number, client, work, total, method in CUSTOMER_INVOICES:
            paid_at = now - timedelta(days=30 * months_ago + days)
            issued = paid_at.date() - timedelta(days=10)
            amount = Decimal(total)

            invoice = Invoice.objects.create(
                organization=org,
                invoice_number=number,
                status=Invoice.Status.PAID,
                issue_date=issued,
                due_date=issued + timedelta(days=14),
                currency="USD",
                subtotal=amount,
                tax=Decimal("0.00"),
                total=amount,
                billing_email=client,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                description=work,
                quantity=Decimal("1"),
                unit_price=amount,
                amount=amount,
            )

            stripe_paid = method == Payment.Method.STRIPE

            payment = Payment.objects.create(
                organization=org,
                invoice=invoice,
                amount=amount,
                currency="USD",
                method=method,
                stripe_checkout_session_id=(
                    f"cs_demo_{number}" if stripe_paid else None
                ),
                recorded_by=None if stripe_paid else owner,
                paid_at=paid_at,
            )

            if number == REFUNDED_INVOICE:
                refunded = Decimal("150.00")
                Refund.objects.create(
                    organization=org,
                    payment=payment,
                    stripe_refund_id="re_demo_1",
                    amount=refunded,
                    currency="USD",
                    status=Refund.Status.SUCCEEDED,
                    reason="requested_by_customer",
                    refunded_at=paid_at + timedelta(days=3),
                )
                payment.amount_refunded = refunded
                payment.status = Payment.Status.PARTIALLY_REFUNDED
                payment.save(update_fields=["amount_refunded", "status"])

    def create_usage(self, org, owner, period_start, now):
        production, _ = ApiKey.create_key(
            organization=org, name="Production server", created_by=owner
        )
        ApiKey.create_key(organization=org, name="Staging", created_by=owner)
        old, _ = ApiKey.create_key(
            organization=org, name="Old mobile app", created_by=owner
        )
        old.revoke(owner)

        days = max((now - period_start).days, 1)
        records = []
        for day in range(days):
            records.append(
                UsageRecord(
                    organization=org,
                    quantity=random.randint(450, 750),
                    api_key=production,
                    endpoint="text.analyze",
                )
            )
        created = UsageRecord.objects.bulk_create(records)

        # recorded_at is auto_now_add: spread the rows over the period.
        for day, record in enumerate(created):
            UsageRecord.objects.filter(pk=record.pk).update(
                recorded_at=period_start + timedelta(days=day, hours=10)
            )
        ApiKey.objects.filter(pk=production.pk).update(last_used_at=now)

    def create_activity(self, org, owner, accountant, member):
        for user, action, description in (
            (owner, "SUBSCRIPTION_UPGRADED", "Upgraded from Free to Pro."),
            (owner, "API_KEY_CREATED", "API key 'Production server' created."),
            (accountant, "INVOICE_CREATED", "Invoice INV-1042 created."),
            (accountant, "INVOICE_MARKED_PAID", "Invoice INV-1037 marked as paid."),
            (owner, "MEMBER_INVITED", "member@demo.com invited as Member."),
        ):
            create_audit_log(
                organization=org,
                user=user,
                action=action,
                description=description,
            )

        for user in (owner, accountant, member):
            Notification.objects.create(
                organization=org,
                user=user,
                notification_type=Notification.NotificationType.PAYMENT_SUCCESS,
                title="Payment Successful",
                message="Your Pro subscription payment of $29.00 was received.",
            )
            Notification.objects.create(
                organization=org,
                user=user,
                notification_type=Notification.NotificationType.USAGE_WARNING,
                title="Usage at 70%",
                message="Acme Analytics has used 70% of this period's API requests.",
            )
