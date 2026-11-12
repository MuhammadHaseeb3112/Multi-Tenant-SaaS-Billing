"""
Invitation management: list with status, resend, revoke, public
preview (for a pre-filled sign-up form), re-inviting removed members,
email failures and the activity log.
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog

from .models import Invitation, Membership
from .tests import TenantsTests as Base


class InvitationManagementTests(APITestCase):
    # Reuse the users/orgs fixture without re-running the base tests.
    setUp = Base.setUp

    def invite(self, email="new@example.com", role=Membership.Role.ACCOUNTANT):
        self.client.force_authenticate(user=self.owner)
        return self.client.post(
            self.invitation_url,
            {"email": email, "role": role},
            format="json",
        )

    def raw_token_from_last_mail(self):
        body = mail.outbox[-1].body
        return body.split("token=")[1].split()[0]

    def detail_url(self, invitation):
        return reverse(
            "organization-invitation-detail",
            kwargs={
                "organization_id": self.organization.id,
                "invitation_id": invitation.id,
            },
        )

    def resend_url(self, invitation):
        return reverse(
            "organization-invitation-resend",
            kwargs={
                "organization_id": self.organization.id,
                "invitation_id": invitation.id,
            },
        )

    # ---------------------------------------------------------------
    # Sending
    # ---------------------------------------------------------------

    def test_email_names_the_invited_address_and_links_to_accept_page(self):
        response = self.invite()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = mail.outbox[-1].body
        self.assertIn("This invitation is for: new@example.com", body)
        self.assertIn("/accept-invitation?token=", body)

    def test_active_member_cannot_be_invited_again(self):
        response = self.invite(email="accountant@example.com")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already a member", response.data["detail"])

    def test_pending_invitation_blocks_a_second_one(self):
        self.invite()
        response = self.invite()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already pending", response.data["detail"])

    def test_email_failure_returns_503_and_keeps_nothing(self):
        with mock.patch(
            "apps.tenants.views.send_mail",
            side_effect=OSError("SMTP down"),
        ):
            response = self.invite()

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        self.assertIn("could not be sent", response.data["detail"])
        self.assertFalse(
            Invitation.objects.filter(email="new@example.com").exists()
        )

    def test_sending_is_in_the_activity_log(self):
        self.invite()

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                action="INVITATION_SENT",
            ).exists()
        )

    # ---------------------------------------------------------------
    # List
    # ---------------------------------------------------------------

    def test_admin_lists_invitations_with_status(self):
        self.invite(email="pending@example.com")
        expired, _ = Invitation.create_invitation(
            organization=self.organization,
            email="old@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )
        expired.expires_at = timezone.now() - timedelta(days=1)
        expired.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.invitation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_email = {row["email"]: row for row in response.data}
        self.assertEqual(by_email["pending@example.com"]["status"], "PENDING")
        self.assertEqual(by_email["old@example.com"]["status"], "EXPIRED")
        self.assertEqual(
            by_email["pending@example.com"]["role"], "ACCOUNTANT"
        )

    def test_member_cannot_list_invitations(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.invitation_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ---------------------------------------------------------------
    # Revoke and resend
    # ---------------------------------------------------------------

    def test_revoke_deletes_pending_invitation_and_link_stops_working(self):
        self.invite()
        token = self.raw_token_from_last_mail()
        invitation = Invitation.objects.get(email="new@example.com")

        response = self.client.delete(self.detail_url(invitation))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Invitation.objects.filter(id=invitation.id).exists())
        preview = self.client.get(
            reverse("invitation-preview"), {"token": token}
        )
        self.assertEqual(preview.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            AuditLog.objects.filter(action="INVITATION_REVOKED").exists()
        )

    def test_resend_gives_new_link_and_new_expiry(self):
        self.invite()
        old_token = self.raw_token_from_last_mail()
        invitation = Invitation.objects.get(email="new@example.com")
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()

        response = self.client.post(self.resend_url(invitation))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invitation"]["status"], "PENDING")
        new_token = self.raw_token_from_last_mail()
        self.assertNotEqual(old_token, new_token)
        self.assertEqual(
            self.client.get(
                reverse("invitation-preview"), {"token": old_token}
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_accepted_invitation_cannot_be_revoked_or_resent(self):
        self.invite()
        invitation = Invitation.objects.get(email="new@example.com")
        invitation.accepted_at = timezone.now()
        invitation.save()

        self.assertEqual(
            self.client.delete(self.detail_url(invitation)).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.resend_url(invitation)).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_other_org_admin_cannot_touch_invitation(self):
        self.invite()
        invitation = Invitation.objects.get(email="new@example.com")
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(self.detail_url(invitation))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Invitation.objects.filter(id=invitation.id).exists())

    # ---------------------------------------------------------------
    # Preview (public)
    # ---------------------------------------------------------------

    def test_preview_shows_email_and_workspace_without_login(self):
        self.invite()
        token = self.raw_token_from_last_mail()
        self.client.force_authenticate(user=None)

        response = self.client.get(
            reverse("invitation-preview"), {"token": token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertEqual(
            response.data["organization_name"], self.organization.name
        )
        self.assertEqual(response.data["role"], "ACCOUNTANT")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertFalse(response.data["account_exists"])
        self.assertNotIn("id", response.data)

    def test_preview_tells_when_account_exists(self):
        self.invite(email="other@example.com")
        token = self.raw_token_from_last_mail()

        response = self.client.get(
            reverse("invitation-preview"), {"token": token}
        )

        self.assertTrue(response.data["account_exists"])

    def test_preview_with_bad_token_is_404(self):
        response = self.client.get(
            reverse("invitation-preview"), {"token": "nope"}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---------------------------------------------------------------
    # Accepting
    # ---------------------------------------------------------------

    def test_removed_member_can_be_invited_back_and_rejoin(self):
        membership = Membership.objects.get(
            organization=self.organization, user=self.member
        )
        membership.is_active = False
        membership.save()

        response = self.invite(
            email="member@example.com", role=Membership.Role.ACCOUNTANT
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        token = self.raw_token_from_last_mail()

        self.client.force_authenticate(user=self.member)
        accept = self.client.post(
            self.accept_invitation_url, {"token": token}, format="json"
        )

        self.assertEqual(accept.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
        self.assertEqual(membership.role, Membership.Role.ACCOUNTANT)
        self.assertTrue(
            AuditLog.objects.filter(action="INVITATION_ACCEPTED").exists()
        )

    def test_signup_through_invitation_is_logged(self):
        self.invite(email="brand.new@example.com")
        token = self.raw_token_from_last_mail()
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("register"),
            {
                "email": "brand.new@example.com",
                "password": "StrongPassword123",
                "first_name": "Brand",
                "last_name": "New",
                "invitation_token": token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="brand.new@example.com")
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=user,
                role=Membership.Role.ACCOUNTANT,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                action="INVITATION_ACCEPTED",
            ).exists()
        )

    # ---------------------------------------------------------------
    # Team changes are logged
    # ---------------------------------------------------------------

    def test_role_change_and_removal_are_logged(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        self.client.patch(url, {"role": "ACCOUNTANT"}, format="json")
        self.client.delete(url)

        actions = set(
            AuditLog.objects.filter(
                organization=self.organization
            ).values_list("action", flat=True)
        )
        self.assertIn("MEMBER_ROLE_CHANGED", actions)
        self.assertIn("MEMBER_REMOVED", actions)
