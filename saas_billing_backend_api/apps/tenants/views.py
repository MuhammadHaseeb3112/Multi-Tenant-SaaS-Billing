from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Invitation, Membership, Organization
from .permissions import (
    IsOrganizationAdmin,
    IsOrganizationMember,
)
from .serializers import (
    AcceptInvitationSerializer,
    CreateInvitationSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    UpdateMembershipSerializer,
)


class OrganizationDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationMember,
    ]

    def get(self, request, organization_id):
        organization = get_object_or_404(
            Organization,
            id=organization_id,
            is_active=True,
        )

        serializer = OrganizationSerializer(organization)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class OrganizationMembersView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def get(self, request, organization_id):
        memberships = Membership.objects.filter(
            organization_id=organization_id,
            is_active=True,
        ).select_related("user")

        serializer = MembershipSerializer(
            memberships,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class MembershipDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def patch(self, request, organization_id, user_id):
        membership = get_object_or_404(
            Membership.objects.select_related("user"),
            organization_id=organization_id,
            user_id=user_id,
            is_active=True,
        )

        current_membership = get_object_or_404(
            Membership,
            organization_id=organization_id,
            user=request.user,
            is_active=True,
        )

        # ADMIN cannot modify OWNER.
        if (
            membership.role == Membership.Role.OWNER
            and current_membership.role != Membership.Role.OWNER
        ):
            return Response(
                {
                    "detail": "Only the owner can modify the owner membership."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UpdateMembershipSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data.get("role")
        new_is_active = serializer.validated_data.get("is_active")


        # ADMIN cannot modify another ADMIN.
        if (
            membership.role == Membership.Role.ADMIN
            and current_membership.role == Membership.Role.ADMIN
        ):
            return Response(
                {
                    "detail": "Only the owner can modify an admin."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Only OWNER can assign/remove OWNER role.
        if (
            new_role == Membership.Role.OWNER
            and current_membership.role != Membership.Role.OWNER
        ):
            return Response(
                {
                    "detail": "Only the owner can assign the Owner role."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Do not allow removing/deactivating the current owner.
        if (
            membership.role == Membership.Role.OWNER
            and new_is_active is False
        ):
            return Response(
                {
                    "detail": "The owner cannot be deactivated."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_role is not None:
            membership.role = new_role

        if new_is_active is not None:
            membership.is_active = new_is_active

        membership.save(
            update_fields=[
                "role",
                "is_active",
                "updated_at",
            ]
        )

        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, organization_id, user_id):
        membership = get_object_or_404(
            Membership,
            organization_id=organization_id,
            user_id=user_id,
            is_active=True,
        )

        current_membership = get_object_or_404(
            Membership,
            organization_id=organization_id,
            user=request.user,
            is_active=True,
        )

        # Nobody can remove the owner.
        if membership.role == Membership.Role.OWNER:
            return Response(
                {
                    "detail": "The owner cannot be removed."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ADMIN cannot remove another ADMIN.
        if (
            membership.role == Membership.Role.ADMIN
            and current_membership.role != Membership.Role.OWNER
        ):
            return Response(
                {
                    "detail": "Only the owner can remove an admin."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        membership.is_active = False
        membership.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        return Response(
            {
                "message": "Member removed successfully."
            },
            status=status.HTTP_200_OK,
        )


class OrganizationInvitationCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    @transaction.atomic
    def post(self, request, organization_id):
        organization = get_object_or_404(
            Organization,
            id=organization_id,
            is_active=True,
        )

        serializer = CreateInvitationSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        role = serializer.validated_data["role"]

        # Check if user is already a member.
        if Membership.objects.filter(
            organization=organization,
            user__email=email,
        ).exists():
            return Response(
                {
                    "detail": "This user is already a member of the organization."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for an existing pending invitation.
        existing_invitation = Invitation.objects.filter(
            organization=organization,
            email=email,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()

        if existing_invitation:
            return Response(
                {
                    "detail": "A pending invitation already exists for this email."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation, raw_token = Invitation.create_invitation(
            organization=organization,
            email=email,
            role=role,
            invited_by=request.user,
            expires_in_days=7,
        )

        if settings.DEBUG:
            print("=" * 70)
            print("INVITATION TOKEN (DEVELOPMENT ONLY)")
            print(raw_token)
            print("=" * 70)

        # Invitation URL.
        # FRONTEND_URL comes from settings (was hardcoded to localhost,
        # so invitation links broke in any deployed environment).
        invitation_url = (
            f"{settings.FRONTEND_URL}/register/"
            f"?token={raw_token}"
        )

        send_mail(
            subject=f"Invitation to join {organization.name}",
            message=(
                f"Hello,\n\n"
                f"You have been invited to join "
                f"{organization.name} as {role}.\n\n"
                f"Accept your invitation using this link:\n"
                f"{invitation_url}\n\n"
                f"This invitation expires in 7 days.\n\n"
                f"If you did not expect this invitation, "
                f"you can safely ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response(
            {
                "message": "Invitation sent successfully.",
                "invitation": {
                    "id": str(invitation.id),
                    "email": invitation.email,
                    "role": invitation.role,
                    "expires_at": invitation.expires_at,
                    "invitation_url": invitation_url,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class AcceptInvitationView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @transaction.atomic
    def post(self, request):
        serializer = AcceptInvitationSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["token"]

        token_hash = Invitation.hash_token(raw_token)

        invitation = (
            Invitation.objects
            .select_for_update()
            .select_related("organization")
            .filter(token_hash=token_hash)
            .first()
        )

        if not invitation:
            return Response(
                {
                    "detail": "Invalid invitation token."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.accepted_at:
            return Response(
                {
                    "detail": "This invitation has already been accepted."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.is_expired:
            return Response(
                {
                    "detail": "This invitation has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not invitation.organization.is_active:
            return Response(
                {
                    "detail": "This organization is no longer active."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Token belongs to a specific email.
        if request.user.email.lower() != invitation.email.lower():
            return Response(
                {
                    "detail": "This invitation was sent to a different email address."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent duplicate membership.
        if Membership.objects.filter(
            organization=invitation.organization,
            user=request.user,
        ).exists():
            return Response(
                {
                    "detail": "You are already a member of this organization."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = Membership.objects.create(
            organization=invitation.organization,
            user=request.user,
            role=invitation.role,
            is_active=True,
        )

        invitation.accepted_at = timezone.now()
        invitation.save(
            update_fields=["accepted_at"]
        )

        return Response(
            {
                "message": "Invitation accepted successfully.",
                "organization": {
                    "id": str(invitation.organization.id),
                    "name": invitation.organization.name,
                    "slug": invitation.organization.slug,
                },
                "membership": {
                    "role": membership.role,
                    "is_active": membership.is_active,
                },
            },
            status=status.HTTP_200_OK,
        )