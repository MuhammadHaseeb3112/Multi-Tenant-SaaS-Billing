from django.urls import path

from .views import (
    OrganizationSubscriptionView,
    PlanListView,
    OrganizationCheckoutView,
    OrganizationSubscriptionChangeView,
    OrganizationSubscriptionCancelView,
    ResumeSubscriptionView,
)


urlpatterns = [
    path(
        "plans/",
        PlanListView.as_view(),
        name="billing-plans",
    ),
    path(
        "organizations/<uuid:organization_id>/subscription/",
        OrganizationSubscriptionView.as_view(),
        name="organization-subscription",
    ),

    path(
        "organizations/<uuid:organization_id>/checkout/",
        OrganizationCheckoutView.as_view(),
        name="organization-checkout",
    ),

    path(
        "organizations/<uuid:organization_id>/subscription/change/",
        OrganizationSubscriptionChangeView.as_view(),
        name="organization-subscription-change",
    ),

    path(
    "organizations/<uuid:organization_id>/subscription/cancel/",
    OrganizationSubscriptionCancelView.as_view(),
    name="organization-subscription-cancel",
    ),

    path(
    "organizations/<uuid:organization_id>/subscription/resume/",
    ResumeSubscriptionView.as_view(),
    name="subscription-resume",
    ),
]
