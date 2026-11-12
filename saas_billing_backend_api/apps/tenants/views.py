import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.security import AuthRateThrottle
from apps.audit.services import create_audit_log

from .models import Invitation, Membership, Organization

logger = logging.getLogger(__name__)
from .permissions import (
    IsOrganizationAdmin,
    IsOrganizationMember,
)
from .serializers import (
    AcceptInvitationSerializer,
    CreateOrganizationSerializer,
    CreateInvitationSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    UpdateMembershipSerializer,
)


class OrganizationCreateView(APIView):
    """
    POST /api/organizations/  {"name": "...", "billing_email": "..."}

    Creates a new workspace owned by the current user: the organization,
    an OWNER membership and a FREE subscription, all in one transaction.
    """

    permission_classes = [IsAuthenticated]

    # Stops one account from creating workspaces without limit.
    MAX_OWNED_ORGANIZATIONS = 10

    def post(self, request):
        from apps.billing.models import Plan, Subscription

        from .utils import unique_organization_slug

        serializer = CreateOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        owned = Membership.objects.filter(
            user=request.user,
            role=Membership.Role.OWNER,
        ).count()

        if owned >= self.MAX_OWNED_ORGANIZATIONS:
            return Response(
                {
                    "detail": (
                        "You can own at most "
                        f"{self.MAX_OWNED_ORGANIZATIONS} workspaces."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        free_plan = Plan.objects.filter(code="FREE", is_active=True).first()

        if free_plan is None:
            return Response(
                {"detail": "No free plan is configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        name = serializer.validated_data["name"]

        with transaction.atomic():
            organization = Organization.objects.create(
                name=name,
                slug=unique_organization_slug(name),
                billing_email=serializer.validated_data.get(
                    "billing_email", request.user.email
                ),
            )

            Membership.objects.create(
                user=request.user,
                organization=organization,
                role=Membership.Role.OWNER,
            )

            Subscription.objects.create(
                organization=organization,
                plan=free_plan,
                status=Subscription.Status.ACTIVE,
                interval=Subscription.Interval.MONTHLY,
            )

            create_audit_log(
                organization=organization,
                user=request.user,
                action="ORGANIZATION_CREATED",
                resource_type="organization",
                resource_id=organization.id,
                description=f"Workspace '{organization.name}' created.",
            )

        return Response(
            {
                "id": str(organization.id),
                "name": organization.name,
                "slug": organization.slug,
                "role": Membership.Role.OWNER,
            },
            status=status.HTTP_201_CREATED,
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

        old_role = membership.role

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

        if new_role is not None and new_role != old_role:
            create_audit_log(
                organization=membership.organization,
                user=request.user,
                action="MEMBER_ROLE_CHANGED",
                resource_type="membership",
                resource_id=membership.id,
                description=(
                    f"{membership.user.email}: {old_role} -> {new_role}."
                ),
                metadata={"from": old_role, "to": new_role},
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

        create_audit_log(
            organization=membership.organization,
            user=request.user,
            action="MEMBER_REMOVED",
            resource_type="membership",
            resource_id=membership.id,
            description=f"{membership.user.email} removed from the workspace.",
        )

        return Response(
            {
                "message": "Member removed successfully."
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# Invitations
# =====================================================================

INVITATION_DAYS = 7


def invitation_status(invitation):
    if invitation.accepted_at:
        return "ACCEPTED"
    if invitation.is_expired:
        return "EXPIRED"
    return "PENDING"


def invitation_link(raw_token):
    return f"{settings.FRONTEND_URL}/accept-invitation?token={raw_token}"


def display_name(user):
    if user is None:
        return None
    full = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full or user.email


def send_invitation_email(invitation, raw_token):
    organization = invitation.organization
    inviter = invitation.invited_by
    inviter_name = display_name(inviter) or "A teammate"

    send_mail(
        subject=f"Invitation to join {organization.name}",
        message=(
            f"Hello,\n\n"
            f"{inviter_name} invited you to join "
            f"{organization.name} as {invitation.role}.\n\n"
            f"This invitation is for: {invitation.email}\n\n"
            f"Accept your invitation using this link:\n"
            f"{invitation_link(raw_token)}\n\n"
            f"This invitation expires in {INVITATION_DAYS} days.\n\n"
            f"If you did not expect this invitation, "
            f"you can safely ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )


def serialize_invitation(invitation):
    inviter = invitation.invited_by
    return {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation_status(invitation),
        "invited_by": display_name(inviter),
        "created_at": invitation.created_at,
        "expires_at": invitation.expires_at,
        "accepted_at": invitation.accepted_at,
    }


EMAIL_FAILED = Response(
    {
        "detail": (
            "The invitation email could not be sent. "
            "Check the email settings and try again."
        )
    },
    status=status.HTTP_503_SERVICE_UNAVAILABLE,
)


class OrganizationInvitationCreateView(APIView):
    """
    GET  - list invitations (pending, accepted, expired) for the team page.
    POST - invite an email address with a role.
    """

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def get(self, request, organization_id):
        invitations = (
            Invitation.objects
            .filter(organization_id=organization_id)
            .select_related("invited_by")
            .order_by("-created_at")[:200]
        )

        return Response(
            [serialize_invitation(invitation) for invitation in invitations],
            status=status.HTTP_200_OK,
        )

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

        # Removed members (inactive) may be invited again.
        if Membership.objects.filter(
            organization=organization,
            user__email__iexact=email,
            is_active=True,
        ).exists():
            return Response(
                {
                    "detail": f"{email} is already a member of this organization."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Invitation.objects.filter(
            organization=organization,
            email=email,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            return Response(
                {
                    "detail": (
                        f"An invitation for {email} is already pending. "
                        "Use Resend in the invitations list."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            invitation, raw_token = Invitation.create_invitation(
                organization=organization,
                email=email,
                role=role,
                invited_by=request.user,
                expires_in_days=INVITATION_DAYS,
            )

            try:
                send_invitation_email(invitation, raw_token)
            except Exception:
                logger.exception("Invitation email failed for %s", email)
                # Keep no half-created invitation the user never got.
                transaction.set_rollback(True)
                return EMAIL_FAILED

            create_audit_log(
                organization=organization,
                user=request.user,
                action="INVITATION_SENT",
                resource_type="invitation",
                resource_id=invitation.id,
                description=f"{email} invited as {role}.",
                metadata={"email": email, "role": role},
            )

        data = {
            "message": "Invitation sent successfully.",
            "invitation": serialize_invitation(invitation),
        }

        # Handy for local testing without an inbox.
        if settings.DEBUG:
            data["invitation"]["invitation_url"] = invitation_link(raw_token)

        return Response(data, status=status.HTTP_201_CREATED)


class OrganizationInvitationDetailView(APIView):
    """DELETE - revoke an invitation that has not been accepted."""

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def delete(self, request, organization_id, invitation_id):
        invitation = get_object_or_404(
            Invitation,
            id=invitation_id,
            organization_id=organization_id,
        )

        if invitation.accepted_at:
            return Response(
                {
                    "detail": (
                        "This invitation was already accepted. "
                        "Remove the member instead."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_audit_log(
            organization=invitation.organization,
            user=request.user,
            action="INVITATION_REVOKED",
            resource_type="invitation",
            resource_id=invitation.id,
            description=f"Invitation for {invitation.email} revoked.",
            metadata={"email": invitation.email},
        )

        invitation.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationInvitationResendView(APIView):
    """POST - new link and 7 more days for a pending or expired invite."""

    permission_classes = [
        IsAuthenticated,
        IsOrganizationAdmin,
    ]

    def post(self, request, organization_id, invitation_id):
        with transaction.atomic():
            invitation = get_object_or_404(
                Invitation.objects.select_for_update(of=("self",)).select_related(
                    "organization", "invited_by"
                ),
                id=invitation_id,
                organization_id=organization_id,
            )

            if invitation.accepted_at:
                return Response(
                    {"detail": "This invitation was already accepted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # A new token makes any older link stop working.
            raw_token = Invitation.generate_token()
            invitation.token_hash = Invitation.hash_token(raw_token)
            invitation.expires_at = timezone.now() + timedelta(
                days=INVITATION_DAYS
            )
            invitation.save(update_fields=["token_hash", "expires_at"])

            try:
                send_invitation_email(invitation, raw_token)
            except Exception:
                logger.exception(
                    "Invitation email failed for %s", invitation.email
                )
                transaction.set_rollback(True)
                return EMAIL_FAILED

            create_audit_log(
                organization=invitation.organization,
                user=request.user,
                action="INVITATION_RESENT",
                resource_type="invitation",
                resource_id=invitation.id,
                description=f"Invitation for {invitation.email} resent.",
                metadata={"email": invitation.email},
            )

        return Response(
            {
                "message": "Invitation resent.",
                "invitation": serialize_invitation(invitation),
            },
            status=status.HTTP_200_OK,
        )


class InvitationPreviewView(APIView):
    """
    GET /api/auth/invitations/preview/?token=...

    Public: whoever holds the link sees which workspace and email it is
    for, so the sign-up form can be pre-filled. Throttled per IP.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def get(self, request):
        raw_token = (request.query_params.get("token") or "").strip()

        invitation = None
        if raw_token:
            invitation = (
                Invitation.objects
                .select_related("organization", "invited_by")
                .filter(token_hash=Invitation.hash_token(raw_token))
                .first()
            )

        if invitation is None or not invitation.organization.is_active:
            return Response(
                {"detail": "This invitation link is not valid."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = serialize_invitation(invitation)
        data.pop("id")
        data["organization_name"] = invitation.organization.name
        data["account_exists"] = User.objects.filter(
            email__iexact=invitation.email
        ).exists()

        return Response(data, status=status.HTTP_200_OK)


class AcceptInvitationView(APIView):
    """Signed-in user accepts an invitation sent to their email."""

    # Guessed by token: limit attempts per IP.
    throttle_classes = [AuthRateThrottle]
    permission_classes = [
        IsAuthenticated,
    ]

    @transaction.atomic
    def post(self, request):
        serializer = AcceptInvitationSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        token_hash = Invitation.hash_token(
            serializer.validated_data["token"]
        )

        invitation = (
            Invitation.objects
            .select_for_update()
            .select_related("organization")
            .filter(token_hash=token_hash)
            .first()
        )

        if not invitation:
            return Response(
                {"detail": "Invalid invitation token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.accepted_at:
            return Response(
                {"detail": "This invitation has already been accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.is_expired:
            return Response(
                {
                    "detail": (
                        "This invitation has expired. "
                        "Ask the workspace admin to resend it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not invitation.organization.is_active:
            return Response(
                {"detail": "This organization is no longer active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.user.email.lower() != invitation.email.lower():
            return Response(
                {
                    "detail": (
                        "This invitation was sent to "
                        f"{invitation.email}. Sign in with that account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        membership = Membership.objects.filter(
            organization=invitation.organization,
            user=request.user,
        ).first()

        if membership and membership.is_active:
            return Response(
                {"detail": "You are already a member of this organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership:
            # Was removed earlier and is now invited back.
            membership.is_active = True
            membership.role = invitation.role
            membership.save(update_fields=["is_active", "role", "updated_at"])
        else:
            membership = Membership.objects.create(
                organization=invitation.organization,
                user=request.user,
                role=invitation.role,
                is_active=True,
            )

        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])

        create_audit_log(
            organization=invitation.organization,
            user=request.user,
            action="INVITATION_ACCEPTED",
            resource_type="membership",
            resource_id=membership.id,
            description=(
                f"{request.user.email} joined as {membership.role}."
            ),
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
