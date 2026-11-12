"""
Account self-service: profile, change password, forgot password.

- PATCH auth/me/                      update first / last name
- POST  auth/password/change/         signed-in user, needs current password
- POST  auth/password/reset/          email a reset link (public)
- GET   auth/password/reset/validate/ is this link still usable? (public)
- POST  auth/password/reset/confirm/  set a new password from the link

Changing or resetting a password signs the account out everywhere
else: every outstanding refresh token is blacklisted, so other devices
cannot get a new access token.
"""

import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.audit.services import create_audit_log

from .models import User
from .security import AuthRateThrottle, LoginLockout, origin_is_trusted

logger = logging.getLogger(__name__)

# Same answer whether or not the email has an account, so the form
# cannot be used to find out who is registered.
RESET_REQUESTED = (
    "If an account exists for that email, a password reset link "
    "has been sent."
)
INVALID_RESET_LINK = (
    "This password reset link is invalid or has expired. "
    "Please request a new one."
)


def revoke_all_sessions(user):
    """Blacklist every refresh token the user still holds."""

    tokens = OutstandingToken.objects.filter(
        user=user,
        expires_at__gt=timezone.now(),
    )

    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)


def audit_for_user(user, action, description):
    """
    Account events are not tied to one workspace, so they are written
    to the activity log of every workspace the user is an active
    member of.
    """

    memberships = user.memberships.filter(
        is_active=True,
        organization__is_active=True,
    ).select_related("organization")

    for membership in memberships:
        create_audit_log(
            organization=membership.organization,
            user=user,
            action=action,
            resource_type="User",
            resource_id=user.id,
            description=description,
        )


def check_new_password(password, user):
    """Run Django's password validators; DRF-style error on failure."""

    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(
            {"new_password": list(error.messages)}
        )


def user_from_reset_link(uid, token):
    """The active user a reset link belongs to, or None."""

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist,
            DjangoValidationError):
        return None

    if not default_token_generator.check_token(user, token):
        return None

    return user


def password_reset_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    return f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"


# ---------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------


class ProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(
        max_length=150,
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name")


class NewPasswordMixin(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "The two passwords do not match."}
            )

        return attrs


class PasswordChangeSerializer(NewPasswordMixin):
    current_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["user"]

        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )

        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {
                    "new_password": (
                        "The new password must be different from the "
                        "current one."
                    )
                }
            )

        check_new_password(attrs["new_password"], user)

        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(NewPasswordMixin):
    uid = serializers.CharField()
    token = serializers.CharField()


# ---------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthRateThrottle]

    @transaction.atomic
    def post(self, request):
        if not origin_is_trusted(request):
            return Response(
                {"detail": "Untrusted origin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])

        # Sign out every other device, then start a fresh session
        # for this one (new refresh cookie + access token).
        revoke_all_sessions(user)

        audit_for_user(
            user,
            "PASSWORD_CHANGED",
            f"{user.email} changed their password.",
        )

        from .views import auth_response

        return auth_response(
            user,
            "Password changed. Other devices have been signed out.",
            status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()

        if user:
            try:
                send_mail(
                    subject="Reset your password",
                    message=(
                        "Hello,\n\n"
                        "We received a request to reset the password "
                        f"for {user.email}.\n\n"
                        "Choose a new password using this link:\n"
                        f"{password_reset_link(user)}\n\n"
                        "The link works once and expires in 1 hour.\n\n"
                        "If you did not ask for this, you can ignore "
                        "this email. Your password will not change."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Never reveal (through an error) that the account
                # exists; the failure is logged for the operator.
                logger.exception("Password reset email failed.")

        return Response(
            {"detail": RESET_REQUESTED},
            status=status.HTTP_200_OK,
        )


class PasswordResetValidateView(APIView):
    """Lets the reset page say 'link expired' before showing a form."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def get(self, request):
        user = user_from_reset_link(
            request.query_params.get("uid", ""),
            request.query_params.get("token", ""),
        )

        if not user:
            return Response(
                {"detail": INVALID_RESET_LINK},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = user_from_reset_link(data["uid"], data["token"])

        if not user:
            return Response(
                {"detail": INVALID_RESET_LINK},
                status=status.HTTP_400_BAD_REQUEST,
            )

        check_new_password(data["new_password"], user)

        # Changing the password also invalidates this link (the token
        # is derived from the password hash), so it works only once.
        user.set_password(data["new_password"])
        user.save(update_fields=["password", "updated_at"])

        revoke_all_sessions(user)

        # A locked-out user who just proved they own the mailbox can
        # sign in again straight away.
        LoginLockout(request, user.email).reset()

        audit_for_user(
            user,
            "PASSWORD_RESET",
            f"{user.email} reset their password by email.",
        )

        return Response(
            {
                "detail": (
                    "Your password has been reset. "
                    "You can now sign in."
                )
            },
            status=status.HTTP_200_OK,
        )
