from django.urls import path

from .views import (
    MembershipDetailView,
    OrganizationDetailView,
    OrganizationInvitationCreateView,
    OrganizationMembersView,
    AcceptInvitationView
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/",
        OrganizationDetailView.as_view(),
        name="organization-detail",
    ),

    path(
        "organizations/<uuid:organization_id>/members/",
        OrganizationMembersView.as_view(),
        name="organization-members",
    ),

    path(
        "organizations/<uuid:organization_id>/members/<uuid:user_id>/",
        MembershipDetailView.as_view(),
        name="membership-detail",
    ),

    path(
        "organizations/<uuid:organization_id>/invitations/",
        OrganizationInvitationCreateView.as_view(),
        name="organization-invitation-create",
    ),

    path(
    "auth/invitations/accept/",
    AcceptInvitationView.as_view(),
    name="accept-invitation",
    ),
]