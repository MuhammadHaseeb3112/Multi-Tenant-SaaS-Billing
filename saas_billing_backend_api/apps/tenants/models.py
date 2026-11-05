import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models

from django.utils import timezone


class Organization(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
    )

    billing_email = models.EmailField(
        max_length=254,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        ACCOUNTANT = "ACCOUNTANT", "Accountant"
        MEMBER = "MEMBER", "Member"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    is_active = models.BooleanField(
        default=True,
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"

class Invitation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )

    email = models.EmailField(
        max_length=254,
    )

    role = models.CharField(
        max_length=20,
        choices=Membership.Role.choices,
        default=Membership.Role.MEMBER,
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )

    token_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    expires_at = models.DateTimeField()

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    @classmethod
    def create_invitation(
        cls,
        organization,
        email,
        role,
        invited_by,
        expires_in_days=7,
    ):
        token = cls.generate_token()

        invitation = cls.objects.create(
            organization=organization,
            email=email.strip().lower(),
            role=role,
            invited_by=invited_by,
            token_hash=cls.hash_token(token),
            expires_at=timezone.now()
            + timedelta(days=expires_in_days),
        )

        return invitation, token

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    def __str__(self):
        return f"{self.email} - {self.organization.name}"