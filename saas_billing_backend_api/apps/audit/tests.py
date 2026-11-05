from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.tenants.models import Organization, Membership

from .models import AuditLog
from .services import create_audit_log


class AuditLogTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="StrongPassword123",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="StrongPassword123",
        )

        self.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-organization",
            billing_email="owner@example.com",
        )

        self.other_organization = Organization.objects.create(
            name="Other Organization",
            slug="other-organization",
            billing_email="other@example.com",
        )

        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        Membership.objects.create(
            user=self.other_user,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
        )

    def test_create_audit_log_service(self):
        audit_log = create_audit_log(
            organization=self.organization,
            user=self.user,
            action="TEST_ACTION",
            resource_type="TEST_RESOURCE",
            resource_id="123",
            description="Test audit log",
            metadata={
                "key": "value",
            },
        )

        self.assertIsNotNone(audit_log.id)
        self.assertEqual(
            audit_log.organization,
            self.organization,
        )
        self.assertEqual(
            audit_log.user,
            self.user,
        )
        self.assertEqual(
            audit_log.action,
            "TEST_ACTION",
        )
        self.assertEqual(
            audit_log.resource_type,
            "TEST_RESOURCE",
        )
        self.assertEqual(
            audit_log.resource_id,
            "123",
        )
        self.assertEqual(
            audit_log.description,
            "Test audit log",
        )
        self.assertEqual(
            audit_log.metadata,
            {"key": "value"},
        )

    def test_audit_log_list_for_organization_member(self):
        create_audit_log(
            organization=self.organization,
            user=self.user,
            action="LOGIN",
            description="User logged in",
        )

        self.client.force_authenticate(
            user=self.user,
        )

        url = reverse(
            "audit-log-list",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["action"],
            "LOGIN",
        )

    def test_audit_log_tenant_isolation(self):
        create_audit_log(
            organization=self.other_organization,
            user=self.other_user,
            action="SECRET_ACTION",
        )

        self.client.force_authenticate(
            user=self.user,
        )

        url = reverse(
            "audit-log-list",
            kwargs={
                "organization_id": self.other_organization.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_audit_log_requires_authentication(self):
        url = reverse(
            "audit-log-list",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_audit_log_returns_only_requested_organization_logs(self):
        create_audit_log(
            organization=self.organization,
            user=self.user,
            action="ORG1_ACTION",
        )

        create_audit_log(
            organization=self.other_organization,
            user=self.other_user,
            action="ORG2_ACTION",
        )

        self.client.force_authenticate(
            user=self.user,
        )

        url = reverse(
            "audit-log-list",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["action"],
            "ORG1_ACTION",
        )