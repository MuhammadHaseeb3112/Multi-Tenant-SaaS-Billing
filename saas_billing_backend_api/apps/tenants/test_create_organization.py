"""
POST /api/organizations/ - a signed-in user creates another workspace.
"""

from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.billing.models import Plan, Subscription

from .models import Membership, Organization
from .views import OrganizationCreateView


class CreateOrganizationTests(APITestCase):

    def setUp(self):
        self.free_plan = Plan.objects.create(
            code="FREE",
            name="Free",
            description="Free plan",
            monthly_price=Decimal("0.00"),
            annual_price=Decimal("0.00"),
            api_request_limit=1000,
            is_active=True,
        )
        self.user = User.objects.create_user(
            email="hassan@example.com",
            password="TestPassword123",
        )
        self.url = reverse("organization-create")

    def test_requires_login(self):
        response = self.client.post(self.url, {"name": "Hassan Labs"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Organization.objects.exists())

    def test_creates_org_owner_membership_and_free_plan(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(self.url, {"name": "  Hassan Labs "})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Hassan Labs")
        self.assertEqual(response.data["slug"], "hassan-labs")
        self.assertEqual(response.data["role"], "OWNER")

        organization = Organization.objects.get(id=response.data["id"])
        self.assertEqual(organization.billing_email, "hassan@example.com")
        self.assertTrue(
            Membership.objects.filter(
                user=self.user,
                organization=organization,
                role=Membership.Role.OWNER,
            ).exists()
        )

        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.plan, self.free_plan)
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

        self.assertTrue(
            AuditLog.objects.filter(
                organization=organization,
                action="ORGANIZATION_CREATED",
            ).exists()
        )

    def test_new_org_appears_in_me(self):
        self.client.force_authenticate(self.user)
        self.client.post(self.url, {"name": "Hassan Labs"})

        me = self.client.get(reverse("me"))

        names = [org["name"] for org in me.data["organizations"]]
        self.assertIn("Hassan Labs", names)

    def test_slug_is_unique(self):
        self.client.force_authenticate(self.user)

        first = self.client.post(self.url, {"name": "Acme"})
        second = self.client.post(self.url, {"name": "Acme"})

        self.assertEqual(first.data["slug"], "acme")
        self.assertEqual(second.data["slug"], "acme-1")

    def test_custom_billing_email(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self.url,
            {"name": "Labs", "billing_email": "billing@labs.com"},
        )

        organization = Organization.objects.get(id=response.data["id"])
        self.assertEqual(organization.billing_email, "billing@labs.com")

    def test_blank_name_is_rejected(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(self.url, {"name": "   "})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Organization.objects.exists())

    def test_limit_on_owned_workspaces(self):
        self.client.force_authenticate(self.user)

        for i in range(OrganizationCreateView.MAX_OWNED_ORGANIZATIONS):
            self.client.post(self.url, {"name": f"Org {i}"})

        response = self.client.post(self.url, {"name": "One too many"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at most", response.data["detail"])

    def test_without_free_plan_nothing_is_created(self):
        self.free_plan.delete()
        self.client.force_authenticate(self.user)

        response = self.client.post(self.url, {"name": "Labs"})

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertFalse(Organization.objects.exists())
