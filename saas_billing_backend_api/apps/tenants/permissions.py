from rest_framework.permissions import BasePermission

from .models import Membership


class IsOrganizationMember(BasePermission):
    def has_permission(self, request, view):
        organization_id = view.kwargs.get("organization_id")

        if not organization_id:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization_id=organization_id,
            is_active=True,
            organization__is_active=True,
        ).exists()


class IsOrganizationAdmin(BasePermission):
    allowed_roles = {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    }

    def has_permission(self, request, view):
        organization_id = view.kwargs.get("organization_id")

        if not organization_id:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization_id=organization_id,
            role__in=self.allowed_roles,
            is_active=True,
            organization__is_active=True,
        ).exists()


class IsOrganizationOwner(BasePermission):
    def has_permission(self, request, view):
        organization_id = view.kwargs.get("organization_id")

        if not organization_id:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization_id=organization_id,
            role=Membership.Role.OWNER,
            is_active=True,
            organization__is_active=True,
        ).exists()

class IsOrganizationFinance(BasePermission):
    """
    Roles allowed to manage invoices and payments:
    OWNER, ADMIN and ACCOUNTANT.

    MEMBER can only read (list invoices, download PDFs).
    """

    allowed_roles = {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.ACCOUNTANT,
    }

    def has_permission(self, request, view):
        organization_id = view.kwargs.get("organization_id")

        if not organization_id:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization_id=organization_id,
            role__in=self.allowed_roles,
            is_active=True,
            organization__is_active=True,
        ).exists()
