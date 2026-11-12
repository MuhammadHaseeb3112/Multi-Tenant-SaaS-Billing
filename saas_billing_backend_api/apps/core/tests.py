import json
import logging
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import create_audit_log
from apps.invoices.models import Payment
from apps.tenants.models import Membership, Organization
from apps.usage.models import ApiKey, UsageRecord

from .logging import JSONFormatter
from .middleware import RequestIDLogFilter, request_id_var


class HealthTests(APITestCase):

    def test_liveness(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    def test_readiness_checks_database_and_cache(self):
        response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["checks"], {"database": "ok", "cache": "ok"}
        )

    def test_readiness_is_503_when_cache_is_down(self):
        with patch("apps.core.health.cache.set", side_effect=OSError("down")):
            response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["checks"]["cache"], "error")


class RequestIDTests(APITestCase):

    def test_generated_when_missing(self):
        response = self.client.get(reverse("health"))

        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_incoming_id_is_kept(self):
        response = self.client.get(
            reverse("health"), HTTP_X_REQUEST_ID="trace-123"
        )

        self.assertEqual(response["X-Request-ID"], "trace-123")

    def test_unsafe_incoming_id_is_replaced(self):
        response = self.client.get(
            reverse("health"), HTTP_X_REQUEST_ID="bad id\nINJECTED"
        )

        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_log_lines_carry_the_request_id_as_json(self):
        token = request_id_var.set("req-42")
        try:
            record = logging.LogRecord(
                "apps.test", logging.WARNING, __file__, 1, "hello %s",
                ("world",), None,
            )
            RequestIDLogFilter().filter(record)
            payload = json.loads(JSONFormatter().format(record))
        finally:
            request_id_var.reset(token)

        self.assertEqual(payload["request_id"], "req-42")
        self.assertEqual(payload["message"], "hello world")
        self.assertEqual(payload["level"], "WARNING")


class BoundedListTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="o@example.com", password="TestPassword123"
        )
        self.org = Organization.objects.create(
            name="Org", slug="org", billing_email="b@example.com"
        )
        Membership.objects.create(
            user=self.user, organization=self.org, role=Membership.Role.OWNER
        )
        AuditLog.objects.bulk_create(
            AuditLog(organization=self.org, action=f"ACTION_{i}")
            for i in range(120)
        )
        self.client.force_authenticate(self.user)
        self.url = reverse(
            "audit-log-list", kwargs={"organization_id": self.org.id}
        )

    def test_audit_log_returns_newest_100_by_default(self):
        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 100)

    def test_limit_param_is_capped(self):
        self.assertEqual(len(self.client.get(self.url + "?limit=5").data), 5)
        self.assertEqual(
            len(self.client.get(self.url + "?limit=99999").data), 120
        )
        self.assertEqual(
            len(self.client.get(self.url + "?limit=abc").data), 100
        )

    def test_newest_first(self):
        create_audit_log(organization=self.org, action="LATEST")

        response = self.client.get(self.url + "?limit=1")

        self.assertEqual(response.data[0]["action"], "LATEST")


class SeedDemoTests(APITestCase):

    def run_seed(self, *args):
        call_command("seed_demo", *args, stdout=StringIO())

    def test_creates_demo_that_can_log_in_with_each_role(self):
        self.run_seed()

        acme = Organization.objects.get(slug="acme-analytics-demo")
        roles = dict(
            Membership.objects.filter(organization=acme)
            .values_list("user__email", "role")
        )
        self.assertEqual(
            roles,
            {
                "owner@demo.com": "OWNER",
                "accountant@demo.com": "ACCOUNTANT",
                "member@demo.com": "MEMBER",
            },
        )
        payments = Payment.objects.filter(organization=acme)

        # 6 subscription payments to the platform, on platform invoices.
        platform = payments.filter(stripe_invoice_id__isnull=False)
        self.assertEqual(platform.count(), 6)
        self.assertFalse(
            platform.filter(invoice__stripe_invoice_id__isnull=True).exists()
        )

        # 9 paid customer invoices, one of them partially refunded.
        customer = payments.filter(stripe_invoice_id__isnull=True)
        self.assertEqual(customer.count(), 9)
        self.assertFalse(
            customer.filter(invoice__stripe_invoice_id__isnull=False).exists()
        )
        self.assertEqual(
            customer.filter(status=Payment.Status.PARTIALLY_REFUNDED).count(),
            1,
        )
        self.assertTrue(UsageRecord.objects.filter(organization=acme).exists())
        self.assertEqual(
            ApiKey.objects.filter(
                organization=acme, revoked_at__isnull=True
            ).count(),
            2,
        )

        response = APIClient().post(
            reverse("login"),
            {"email": "member@demo.com", "password": "DemoPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_demo_fills_the_customer_revenue_figures(self):
        self.run_seed()

        acme = Organization.objects.get(slug="acme-analytics-demo")
        client = APIClient()
        client.force_authenticate(User.objects.get(email="owner@demo.com"))

        response = client.get(
            reverse(
                "analytics-overview",
                kwargs={"organization_id": acme.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        # 8840 invoiced and paid, minus the 150 refund.
        self.assertEqual(
            Decimal(str(response.data["collected_from_customers"])),
            Decimal("8690.00"),
        )
        # 6 x 29 subscription fees.
        self.assertEqual(
            Decimal(str(response.data["paid_to_platform"])),
            Decimal("174.00"),
        )
        self.assertEqual(response.data["open_invoices"]["count"], 2)

    def test_is_idempotent_and_reset_recreates(self):
        self.run_seed()
        self.run_seed()  # second run: no duplicates
        self.assertEqual(
            Organization.objects.filter(slug="acme-analytics-demo").count(), 1
        )

        self.run_seed("--reset")
        self.assertEqual(
            User.objects.filter(email__endswith="@demo.com").count(), 3
        )

    def test_reset_never_touches_real_data(self):
        real = Organization.objects.create(
            name="Real Co", slug="real-co", billing_email="x@real.com"
        )
        User.objects.create_user(email="ceo@real.com", password="x")

        self.run_seed("--reset")

        self.assertTrue(Organization.objects.filter(pk=real.pk).exists())
        self.assertTrue(User.objects.filter(email="ceo@real.com").exists())
