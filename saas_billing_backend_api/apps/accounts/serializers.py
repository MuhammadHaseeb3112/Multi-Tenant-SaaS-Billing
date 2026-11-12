from django.db import transaction
from django.utils import timezone

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .models import User
from apps.tenants.models import (
    Invitation,
    Membership,
    Organization,
)

from apps.billing.models import Plan, Subscription

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    organization_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=False,
    )

    invitation_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        email = attrs["email"]
        invitation_token = attrs.get("invitation_token")

        # ---------------------------------------------------------
        # NORMAL REGISTRATION
        # ---------------------------------------------------------
        if not invitation_token:
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError(
                    {
                        "email": "A user with this email already exists."
                    }
                )

            if not attrs.get("organization_name"):
                raise serializers.ValidationError(
                    {
                        "organization_name": (
                            "Organization name is required for normal registration."
                        )
                    }
                )

            return attrs

        # ---------------------------------------------------------
        # INVITATION REGISTRATION
        # ---------------------------------------------------------

        token_hash = Invitation.hash_token(invitation_token)

        invitation = (
            Invitation.objects
            .select_related("organization")
            .filter(token_hash=token_hash)
            .first()
        )

        if invitation is None:
            raise serializers.ValidationError(
                {
                    "invitation_token": "Invalid invitation token."
                }
            )

        if invitation.is_accepted:
            raise serializers.ValidationError(
                {
                    "invitation_token": "This invitation has already been accepted."
                }
            )

        if invitation.is_expired:
            raise serializers.ValidationError(
                {
                    "invitation_token": "This invitation has expired."
                }
            )

        if not invitation.organization.is_active:
            raise serializers.ValidationError(
                {
                    "invitation_token": (
                        "This organization is no longer active."
                    )
                }
            )

        # The registration email MUST match the invitation email.
        if email.lower() != invitation.email.lower():
            raise serializers.ValidationError(
                {
                    "email": (
                        "This email does not match the invitation."
                    )
                }
            )

        # Registration is only for a NEW user.
        # Existing users should log in and use the invitation
        # acceptance endpoint.
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {
                    "email": (
                        "A user with this email already exists. "
                        "Please log in and accept the invitation."
                    )
                }
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        invitation_token = validated_data.pop(
            "invitation_token",
            None,
        )

        password = validated_data.pop("password")

        # =========================================================
        # INVITATION REGISTRATION
        # =========================================================
        if invitation_token:
            token_hash = Invitation.hash_token(invitation_token)

            # Lock the invitation so two requests cannot accept
            # the same invitation at the same time.
            invitation = (
                Invitation.objects
                .select_for_update()
                .select_related("organization")
                .filter(token_hash=token_hash)
                .first()
            )

            if invitation is None:
                raise serializers.ValidationError(
                    {
                        "invitation_token": "Invalid invitation token."
                    }
                )

            # Re-check everything inside the transaction.
            if invitation.is_accepted:
                raise serializers.ValidationError(
                    {
                        "invitation_token": (
                            "This invitation has already been accepted."
                        )
                    }
                )

            if invitation.is_expired:
                raise serializers.ValidationError(
                    {
                        "invitation_token": (
                            "This invitation has expired."
                        )
                    }
                )

            if not invitation.organization.is_active:
                raise serializers.ValidationError(
                    {
                        "invitation_token": (
                            "This organization is no longer active."
                        )
                    }
                )

            email = validated_data["email"]

            if email.lower() != invitation.email.lower():
                raise serializers.ValidationError(
                    {
                        "email": (
                            "This email does not match the invitation."
                        )
                    }
                )

            # Do not allow duplicate users.
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError(
                    {
                        "email": (
                            "A user with this email already exists. "
                            "Please log in and accept the invitation."
                        )
                    }
                )

            # organization_name is irrelevant for invitation signup.
            validated_data.pop("organization_name", None)

            # Create the user.
            user = User.objects.create_user(
                password=password,
                **validated_data,
            )

            # Create membership in the EXISTING organization.
            membership = Membership.objects.create(
                user=user,
                organization=invitation.organization,
                role=invitation.role,
            )

            # Mark invitation as used.
            invitation.accepted_at = timezone.now()
            invitation.save(
                update_fields=["accepted_at"]
            )

            from apps.audit.services import create_audit_log

            create_audit_log(
                organization=invitation.organization,
                user=user,
                action="INVITATION_ACCEPTED",
                resource_type="membership",
                resource_id=membership.id,
                description=f"{user.email} joined as {membership.role}.",
            )

            return user

        # =========================================================
        # NORMAL REGISTRATION
        # =========================================================

        organization_name = validated_data.pop(
            "organization_name"
        )

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        organization = Organization.objects.create(
            name=organization_name,
            slug=self._generate_slug(organization_name),
            billing_email=user.email,
        )

        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.Role.OWNER,
        )

        # Every new organization starts on the Free plan.
        free_plan = Plan.objects.get(
            code="FREE",
            is_active=True,
        )

        Subscription.objects.create(
            organization=organization,
            plan=free_plan,
            status=Subscription.Status.ACTIVE,
            interval=Subscription.Interval.MONTHLY,
        )

        return user

    def _generate_slug(self, organization_name):
        from apps.tenants.utils import unique_organization_slug

        return unique_organization_slug(organization_name)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if user is None:
            raise AuthenticationFailed(
                "Invalid email or password."
            )

        if not user.is_active:
            raise AuthenticationFailed(
                "This account is inactive."
            )

        attrs["user"] = user

        return attrs
        

class MeSerializer(serializers.ModelSerializer):
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "organizations",
        )

    def get_organizations(self, user):
        memberships = user.memberships.filter(
            is_active=True,
            organization__is_active=True,
        ).select_related("organization")

        return [
            {
                "id": str(membership.organization.id),
                "name": membership.organization.name,
                "slug": membership.organization.slug,
                "role": membership.role,
            }
            for membership in memberships
        ]





class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs):
        token = RefreshToken(self.token)
        token.blacklist()