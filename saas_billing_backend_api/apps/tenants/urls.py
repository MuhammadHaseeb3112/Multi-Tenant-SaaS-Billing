from django.urls import path

from .views import (
    MembershipDetailView,
    OrganizationCreateView,
    OrganizationDetailView,
    InvitationPreviewView,
    OrganizationInvitationCreateView,
    OrganizationInvitationDetailView,
    OrganizationInvitationResendView,
    OrganizationMembersView,
    AcceptInvitationView,
)


urlpatterns = [
    path(
        "organizations/",
        OrganizationCreateView.as_view(),
        name="organization-create",
    ),

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
        "organizations/<uuid:organization_id>/invitations/<uuid:invitation_id>/",
        OrganizationInvitationDetailView.as_view(),
        name="organization-invitation-detail",
    ),

    path(
        "organizations/<uuid:organization_id>/invitations/<uuid:invitation_id>/resend/",
        OrganizationInvitationResendView.as_view(),
        name="organization-invitation-resend",
    ),

    path(
        "auth/invitations/preview/",
        InvitationPreviewView.as_view(),
        name="invitation-preview",
    ),

    path(
        "auth/invitations/accept/",
        AcceptInvitationView.as_view(),
        name="accept-invitation",
    ),
]