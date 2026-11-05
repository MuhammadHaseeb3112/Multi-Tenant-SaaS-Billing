from django.urls import path

from .views import (
    ApiKeyListCreateView,
    ApiKeyRevokeView,
    OverageChargeListView,
    RecordUsageView,
    UsageSummaryView,
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/record/",
        RecordUsageView.as_view(),
        name="usage-record",
    ),
    path(
        "organizations/<uuid:organization_id>/api-keys/",
        ApiKeyListCreateView.as_view(),
        name="api-key-list",
    ),
    path(
        "organizations/<uuid:organization_id>/api-keys/<uuid:key_id>/",
        ApiKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
    path(
        "organizations/<uuid:organization_id>/overage-charges/",
        OverageChargeListView.as_view(),
        name="overage-charge-list",
    ),
    path(
        "organizations/<uuid:organization_id>/",
        UsageSummaryView.as_view(),
        name="usage-summary",
    ),
]
