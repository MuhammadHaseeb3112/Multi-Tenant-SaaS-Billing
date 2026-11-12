"""
The audit log is read-only in the Django admin, even for superusers.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.tenants.models import Organization

from .models import AuditLog


class AuditLogAdminReadOnlyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="root@example.com",
            password="TestPassword123",
        )
        self.client.force_login(self.admin)

        organization = Organization.objects.create(
            name="Acme", slug="acme",
        )
        self.log = AuditLog.objects.create(
            organization=organization,
            user=self.admin,
            action="INVOICE_CREATED",
            resource_type="Invoice",
            resource_id="1",
            description="Invoice INV-000001 created.",
        )

    def test_list_and_detail_can_be_viewed(self):
        response = self.client.get(
            reverse("admin:audit_auditlog_changelist")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INVOICE_CREATED")

        response = self.client.get(
            reverse("admin:audit_auditlog_change", args=[self.log.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_cannot_add(self):
        response = self.client.get(reverse("admin:audit_auditlog_add"))
        self.assertEqual(response.status_code, 403)

    def test_cannot_edit(self):
        response = self.client.post(
            reverse("admin:audit_auditlog_change", args=[self.log.pk]),
            {"description": "tampered"},
        )
        self.assertEqual(response.status_code, 403)

        self.log.refresh_from_db()
        self.assertEqual(
            self.log.description, "Invoice INV-000001 created.",
        )

    def test_cannot_delete(self):
        response = self.client.post(
            reverse("admin:audit_auditlog_delete", args=[self.log.pk]),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(pk=self.log.pk).exists())

        # Bulk "delete selected" is gone too.
        response = self.client.post(
            reverse("admin:audit_auditlog_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [str(self.log.pk)],
                "post": "yes",
            },
        )
        self.assertTrue(AuditLog.objects.filter(pk=self.log.pk).exists())
