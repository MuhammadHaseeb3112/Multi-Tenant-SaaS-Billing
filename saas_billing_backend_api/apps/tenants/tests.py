from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Invitation, Membership, Organization


class TenantsTests(APITestCase):

    def setUp(self):
        self.password = "StrongPassword123"

        # -----------------------------------------------------
        # USERS
        # -----------------------------------------------------

        self.owner = User.objects.create_user(
            email="owner@example.com",
            password=self.password,
            first_name="Owner",
            last_name="User",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password=self.password,
            first_name="Admin",
            last_name="User",
        )

        self.accountant = User.objects.create_user(
            email="accountant@example.com",
            password=self.password,
            first_name="Accountant",
            last_name="User",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password=self.password,
            first_name="Member",
            last_name="User",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password=self.password,
            first_name="Other",
            last_name="User",
        )

        # -----------------------------------------------------
        # ORGANIZATIONS
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # MEMBERSHIPS
        # -----------------------------------------------------

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        Membership.objects.create(
            user=self.admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
        )

        Membership.objects.create(
            user=self.accountant,
            organization=self.organization,
            role=Membership.Role.ACCOUNTANT,
        )

        Membership.objects.create(
            user=self.member,
            organization=self.organization,
            role=Membership.Role.MEMBER,
        )

        Membership.objects.create(
            user=self.other_user,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
        )

        # -----------------------------------------------------
        # URLS
        # -----------------------------------------------------

        self.organization_url = reverse(
            "organization-detail",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        self.other_organization_url = reverse(
            "organization-detail",
            kwargs={
                "organization_id": self.other_organization.id,
            },
        )

        self.members_url = reverse(
            "organization-members",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        self.invitation_url = reverse(
            "organization-invitation-create",
            kwargs={
                "organization_id": self.organization.id,
            },
        )

        self.accept_invitation_url = reverse(
            "accept-invitation",
        )

    # =========================================================
    # ORGANIZATION
    # =========================================================

    def test_organization_member_can_view_organization(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.organization_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["name"],
            "Test Organization",
        )

        self.assertEqual(
            response.data["slug"],
            "test-organization",
        )

    def test_unauthenticated_user_cannot_view_organization(self):
        response = self.client.get(
            self.organization_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_cross_tenant_user_cannot_view_organization(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            self.organization_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_inactive_organization_cannot_be_accessed(self):
        self.organization.is_active = False
        self.organization.save()

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.get(
            self.organization_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # MEMBERS - RBAC
    # =========================================================

    def test_owner_can_list_members(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            4,
        )

    def test_admin_can_list_members(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_accountant_cannot_list_members(self):
        self.client.force_authenticate(
            user=self.accountant
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_cannot_list_members(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cross_tenant_admin_access_is_forbidden(self):
        self.client.force_authenticate(
            user=self.other_user
        )

        response = self.client.get(
            self.members_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # MEMBERSHIP UPDATE
    # =========================================================

    def test_owner_can_change_member_role(self):
        self.client.force_authenticate(
            user=self.owner
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.ACCOUNTANT,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.member.refresh_from_db()

        self.assertEqual(
            self.member.memberships.get(
                organization=self.organization
            ).role,
            Membership.Role.ACCOUNTANT,
        )

    def test_admin_can_change_member_role(self):
        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.ACCOUNTANT,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_admin_cannot_modify_another_admin(self):
        second_admin = User.objects.create_user(
            email="secondadmin@example.com",
            password=self.password,
        )

        Membership.objects.create(
            user=second_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
        )

        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": second_admin.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_cannot_modify_owner(self):
        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.owner.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_cannot_assign_owner_role(self):
        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.OWNER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_can_assign_owner_role(self):
        self.client.force_authenticate(
            user=self.owner
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "role": Membership.Role.OWNER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_owner_cannot_be_deactivated(self):
        self.client.force_authenticate(
            user=self.owner
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.owner.id,
            },
        )

        response = self.client.patch(
            url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # MEMBERSHIP DELETE
    # =========================================================

    def test_owner_can_remove_member(self):
        self.client.force_authenticate(
            user=self.owner
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        membership = Membership.objects.get(
            organization=self.organization,
            user=self.member,
        )

        self.assertFalse(
            membership.is_active
        )

    def test_admin_can_remove_member(self):
        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.member.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_admin_cannot_remove_admin(self):
        self.client.force_authenticate(
            user=self.admin
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.admin.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_cannot_be_removed(self):
        self.client.force_authenticate(
            user=self.owner
        )

        url = reverse(
            "membership-detail",
            kwargs={
                "organization_id": self.organization.id,
                "user_id": self.owner.id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # INVITATIONS
    # =========================================================

    def test_owner_can_send_invitation(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.invitation_url,
            {
                "email": "newmember@example.com",
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["message"],
            "Invitation sent successfully.",
        )

        self.assertEqual(
            response.data["invitation"]["email"],
            "newmember@example.com",
        )

        self.assertEqual(
            response.data["invitation"]["role"],
            Membership.Role.MEMBER,
        )

        self.assertTrue(
            Invitation.objects.filter(
                organization=self.organization,
                email="newmember@example.com",
            ).exists()
        )

        self.assertEqual(
            len(mail.outbox),
            1,
        )

    def test_admin_can_send_invitation(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.post(
            self.invitation_url,
            {
                "email": "accountant2@example.com",
                "role": Membership.Role.ACCOUNTANT,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_member_cannot_send_invitation(self):
        self.client.force_authenticate(
            user=self.member
        )

        response = self.client.post(
            self.invitation_url,
            {
                "email": "newmember@example.com",
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_invite_existing_member(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.invitation_url,
            {
                "email": "member@example.com",
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_create_duplicate_pending_invitation(self):
        Invitation.create_invitation(
            organization=self.organization,
            email="pending@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.invitation_url,
            {
                "email": "pending@example.com",
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # ACCEPT INVITATION
    # =========================================================

    def test_user_can_accept_valid_invitation(self):
        invited_user = User.objects.create_user(
            email="invited@example.com",
            password=self.password,
        )

        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="invited@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        self.client.force_authenticate(
            user=invited_user
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["message"],
            "Invitation accepted successfully.",
        )

        self.assertEqual(
            response.data["membership"]["role"],
            Membership.Role.MEMBER,
        )

        invitation.refresh_from_db()

        self.assertIsNotNone(
            invitation.accepted_at
        )

        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=invited_user,
                role=Membership.Role.MEMBER,
                is_active=True,
            ).exists()
        )

    def test_invalid_invitation_token_is_rejected(self):
        self.client.force_authenticate(
            user=self.owner
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": "invalid-token",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_already_accepted_invitation_is_rejected(self):
        invited_user = User.objects.create_user(
            email="accepted@example.com",
            password=self.password,
        )

        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="accepted@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        invitation.accepted_at = timezone.now()
        invitation.save(
            update_fields=["accepted_at"]
        )

        self.client.force_authenticate(
            user=invited_user
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_expired_invitation_is_rejected(self):
        invited_user = User.objects.create_user(
            email="expired@example.com",
            password=self.password,
        )

        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="expired@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        invitation.expires_at = timezone.now() - timedelta(
            days=1
        )
        invitation.save(
            update_fields=["expires_at"]
        )

        self.client.force_authenticate(
            user=invited_user
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_wrong_email_cannot_accept_invitation(self):
        invited_user = User.objects.create_user(
            email="wrong@example.com",
            password=self.password,
        )

        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="correct@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        self.client.force_authenticate(
            user=invited_user
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_duplicate_membership_cannot_accept_invitation(self):
        invited_user = User.objects.create_user(
            email="existing@example.com",
            password=self.password,
        )

        Membership.objects.create(
            user=invited_user,
            organization=self.organization,
            role=Membership.Role.MEMBER,
        )

        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="existing@example.com",
            role=Membership.Role.ADMIN,
            invited_by=self.owner,
        )

        self.client.force_authenticate(
            user=invited_user
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unauthenticated_user_cannot_accept_invitation(self):
        invitation, raw_token = Invitation.create_invitation(
            organization=self.organization,
            email="anonymous@example.com",
            role=Membership.Role.MEMBER,
            invited_by=self.owner,
        )

        response = self.client.post(
            self.accept_invitation_url,
            {
                "token": raw_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


    @override_settings(FRONTEND_URL="https://app.example.com")
    def test_invitation_email_links_to_configured_frontend(self):
        # Was hardcoded to http://localhost:5173, so links broke in any
        # deployed environment.
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.invitation_url,
            {
                "email": "linked@example.com",
                "role": Membership.Role.MEMBER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://app.example.com/accept-invitation?token=",
            mail.outbox[0].body,
        )
        self.assertNotIn("localhost", mail.outbox[0].body)
