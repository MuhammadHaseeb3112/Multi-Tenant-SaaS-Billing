from django.contrib import admin

from .models import Invitation, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "billing_email",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "billing_email",
    )

    list_filter = (
        "is_active",
    )

    ordering = (
        "-created_at",
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "organization",
        "role",
        "is_active",
        "joined_at",
    )

    search_fields = (
        "user__email",
        "organization__name",
    )

    list_filter = (
        "role",
        "is_active",
    )

    ordering = (
        "-joined_at",
    )


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "organization",
        "role",
        "invited_by",
        "expires_at",
        "accepted_at",
        "created_at",
    )

    search_fields = (
        "email",
        "organization__name",
    )

    list_filter = (
        "role",
        "accepted_at",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "token_hash",
        "created_at",
    )