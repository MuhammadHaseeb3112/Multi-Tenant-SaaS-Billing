from rest_framework import serializers

from .models import Invitation, Membership, Organization



class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "billing_email",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
        )


class MembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(
        source="user.id",
        read_only=True,
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    first_name = serializers.CharField(
        source="user.first_name",
        read_only=True,
    )

    last_name = serializers.CharField(
        source="user.last_name",
        read_only=True,
    )

    class Meta:
        model = Membership
        fields = (
            "user_id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "joined_at",
        )
        read_only_fields = (
            "user_id",
            "email",
            "first_name",
            "last_name",
            "joined_at",
        )


class UpdateMembershipSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=Membership.Role.choices,
        required=False,
    )

    is_active = serializers.BooleanField(
        required=False,
    )


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = (
            "id",
            "email",
            "role",
            "expires_at",
            "accepted_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "expires_at",
            "accepted_at",
            "created_at",
        )


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    role = serializers.ChoiceField(
        choices=[
            (Membership.Role.ADMIN, "Admin"),
            (Membership.Role.ACCOUNTANT, "Accountant"),
            (Membership.Role.MEMBER, "Member"),
        ]
    )

    def validate_email(self, value):
        return value.strip().lower()

class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=500,
    )


class CreateOrganizationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    billing_email = serializers.EmailField(required=False)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name is required.")
        return value.strip()
