from datetime import date
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.tenants.models import Membership, Organization

from .models import Notification
from .serializers import NotificationSerializer
from .services import (
    create_notification,
    create_notification_for_organization_members,
)


class NotificationTestBase(APITestCase):

    def setUp(self):
        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="TestPassword123",
            first_name="Owner",
            last_name="User",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123",
            first_name="Admin",
            last_name="User",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123",
            first_name="Member",
            last_name="User",
        )

        self.other_owner = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123",
            first_name="Other",
            last_name="Owner",
        )

        # ---------------------------------------------------------
        # Organization 1
        # ---------------------------------------------------------

        self.organization = Organization.objects.create(
            name="Acme Corporation",
            slug="acme-corporation",
            billing_email="billing@acme.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        Membership.objects.create(
            user=self.admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        )

        Membership.objects.create(
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Organization 2
        # ---------------------------------------------------------

        self.other_organization = Organization.objects.create(
            name="Other Corporation",
            slug="other-corporation",
            billing_email="billing@other.com",
            is_active=True,
        )

        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        # ---------------------------------------------------------
        # Notifications
        # ---------------------------------------------------------

        self.notification = Notification.objects.create(
            user=self.owner,
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.PAYMENT_SUCCESS
            ),
            title="Payment Successful",
            message="Your payment was successful.",
        )

        self.read_notification = Notification.objects.create(
            user=self.owner,
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.INVOICE_CREATED
            ),
            title="Invoice Created",
            message="A new invoice was created.",
            is_read=True,
            read_at=timezone.now(),
        )

        self.member_notification = Notification.objects.create(
            user=self.member,
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.USAGE_WARNING
            ),
            title="Usage Warning",
            message="You are approaching your usage limit.",
        )

        self.other_notification = Notification.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            notification_type=(
                Notification.NotificationType.PAYMENT_SUCCESS
            ),
            title="Other Payment",
            message="Other organization payment.",
        )

    # -------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------

    def authenticate(self, user):
        response = self.client.post(
            reverse("login"),
            {
                "email": user.email,
                "password": "TestPassword123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {response.data['tokens']['access']}"
            )
        )

    def clear_auth(self):
        self.client.credentials()

    # -------------------------------------------------------------
    # URL helpers
    # -------------------------------------------------------------

    def list_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "notification-list",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def unread_count_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "notification-unread-count",
            kwargs={
                "organization_id": organization.id,
            },
        )

    def mark_read_url(
        self,
        notification=None,
        organization=None,
    ):
        notification = notification or self.notification
        organization = organization or notification.organization

        return reverse(
            "notification-mark-read",
            kwargs={
                "organization_id": organization.id,
                "notification_id": notification.id,
            },
        )

    def mark_all_read_url(self, organization=None):
        organization = organization or self.organization

        return reverse(
            "notification-mark-all-read",
            kwargs={
                "organization_id": organization.id,
            },
        )


class NotificationModelTests(NotificationTestBase):

    def test_notification_string_representation(self):
        self.assertEqual(
            str(self.notification),
            "Payment Successful - owner@example.com",
        )

    def test_notification_defaults_to_unread(self):
        notification = Notification.objects.create(
            user=self.owner,
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.PAYMENT_FAILED
            ),
            title="Payment Failed",
            message="Your payment failed.",
        )

        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_notification_uuid_is_generated(self):
        self.assertIsNotNone(self.notification.id)


class NotificationSerializerTests(NotificationTestBase):

    def test_serializer_returns_expected_fields(self):
        serializer = NotificationSerializer(
            self.notification
        )

        self.assertEqual(
            set(serializer.data.keys()),
            {
                "id",
                "organization",
                "notification_type",
                "title",
                "message",
                "is_read",
                "read_at",
                "created_at",
            },
        )

    def test_all_notification_fields_are_read_only(self):
        serializer = NotificationSerializer(
            self.notification
        )

        self.assertEqual(
            set(serializer.Meta.read_only_fields),
            set(serializer.Meta.fields),
        )


class NotificationServiceTests(NotificationTestBase):

    def test_create_notification(self):
        notification = create_notification(
            organization=self.organization,
            user=self.owner,
            notification_type=(
                Notification.NotificationType.SUBSCRIPTION_UPDATED
            ),
            title="Subscription Updated",
            message="Your subscription was updated.",
        )

        self.assertIsNotNone(notification.id)

        self.assertEqual(
            notification.organization,
            self.organization,
        )

        self.assertEqual(
            notification.user,
            self.owner,
        )

        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.SUBSCRIPTION_UPDATED,
        )

        self.assertFalse(notification.is_read)

    def test_create_notification_for_all_active_members(self):
        created = create_notification_for_organization_members(
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.INVOICE_CREATED
            ),
            title="Invoice Created",
            message="A new invoice was created.",
        )

        self.assertEqual(
            len(created),
            3,
        )

        user_ids = {
            notification.user_id
            for notification in created
        }

        self.assertEqual(
            user_ids,
            {
                self.owner.id,
                self.admin.id,
                self.member.id,
            },
        )

    def test_bulk_notification_is_unread_by_default(self):
        created = create_notification_for_organization_members(
            organization=self.organization,
            notification_type=(
                Notification.NotificationType.USAGE_WARNING
            ),
            title="Usage Warning",
            message="Usage warning.",
        )

        self.assertTrue(
            all(
                notification.is_read is False
                for notification in created
            )
        )


class NotificationListTests(NotificationTestBase):

    def test_authenticated_user_can_list_notifications(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.list_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

    def test_list_returns_only_current_users_notifications(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.list_url()
        )

        notification_ids = {
            item["id"]
            for item in response.data
        }

        self.assertIn(
            str(self.notification.id),
            notification_ids,
        )

        self.assertIn(
            str(self.read_notification.id),
            notification_ids,
        )

        self.assertNotIn(
            str(self.member_notification.id),
            notification_ids,
        )

        self.assertNotIn(
            str(self.other_notification.id),
            notification_ids,
        )

    def test_cross_tenant_list_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.list_url(self.organization)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_list_notifications(self):
        self.clear_auth()

        response = self.client.get(
            self.list_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class NotificationUnreadCountTests(NotificationTestBase):

    def test_unread_count(self):
        self.authenticate(self.owner)

        response = self.client.get(
            self.unread_count_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["unread_count"],
            1,
        )

    def test_unread_count_excludes_read_notifications(self):
        self.notification.is_read = True
        self.notification.read_at = timezone.now()
        self.notification.save(
            update_fields=["is_read", "read_at"]
        )

        self.authenticate(self.owner)

        response = self.client.get(
            self.unread_count_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["unread_count"],
            0,
        )

    def test_cross_tenant_unread_count_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.get(
            self.unread_count_url(self.organization)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_get_unread_count(self):
        self.clear_auth()

        response = self.client.get(
            self.unread_count_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class MarkNotificationReadTests(NotificationTestBase):

    def test_user_can_mark_notification_as_read(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.mark_read_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["is_read"],
            True,
        )

        self.notification.refresh_from_db()

        self.assertTrue(
            self.notification.is_read
        )

        self.assertIsNotNone(
            self.notification.read_at
        )

    def test_mark_read_sets_read_at(self):
        self.authenticate(self.owner)

        before = timezone.now()

        response = self.client.post(
            self.mark_read_url()
        )

        after = timezone.now()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.notification.refresh_from_db()

        self.assertGreaterEqual(
            self.notification.read_at,
            before,
        )

        self.assertLessEqual(
            self.notification.read_at,
            after,
        )

    def test_mark_already_read_is_idempotent(self):
        original_read_at = self.read_notification.read_at

        self.authenticate(self.owner)

        response = self.client.post(
            self.mark_read_url(
                notification=self.read_notification
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["is_read"],
            True,
        )

        self.read_notification.refresh_from_db()

        self.assertEqual(
            self.read_notification.read_at,
            original_read_at,
        )

    def test_user_cannot_mark_another_users_notification(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.mark_read_url(
                notification=self.member_notification
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cross_tenant_notification_cannot_be_marked_read(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.mark_read_url(
                notification=self.notification,
                organization=self.organization,
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_mark_notification_read(self):
        self.clear_auth()

        response = self.client.post(
            self.mark_read_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class MarkAllNotificationsReadTests(NotificationTestBase):

    def test_user_can_mark_all_notifications_as_read(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.mark_all_read_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["updated_count"],
            1,
        )

        unread_count = Notification.objects.filter(
            organization=self.organization,
            user=self.owner,
            is_read=False,
        ).count()

        self.assertEqual(
            unread_count,
            0,
        )

    def test_mark_all_read_only_affects_current_user(self):
        self.authenticate(self.owner)

        self.client.post(
            self.mark_all_read_url()
        )

        self.member_notification.refresh_from_db()

        self.assertFalse(
            self.member_notification.is_read
        )

    def test_mark_all_read_is_idempotent(self):
        self.authenticate(self.owner)

        first_response = self.client.post(
            self.mark_all_read_url()
        )

        second_response = self.client.post(
            self.mark_all_read_url()
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second_response.data["updated_count"],
            0,
        )

    def test_cross_tenant_mark_all_read_is_forbidden(self):
        self.authenticate(self.other_owner)

        response = self.client.post(
            self.mark_all_read_url(self.organization)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_mark_all_read(self):
        self.clear_auth()

        response = self.client.post(
            self.mark_all_read_url()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )