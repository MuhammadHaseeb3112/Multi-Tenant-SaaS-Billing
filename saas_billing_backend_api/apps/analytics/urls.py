from django.urls import path

from .views import (
    MRRView,
    SubscriptionAnalyticsView,
    RevenueTrendView,
    ChurnView,
    AnalyticsOverviewView,
    PlatformOverviewView,
)


urlpatterns = [
    path(
        "platform/overview/",
        PlatformOverviewView.as_view(),
        name="analytics-platform-overview",
    ),

    path(
        "organizations/<uuid:organization_id>/mrr/",
        MRRView.as_view(),
        name="analytics-mrr",
    ),

    path(
        "organizations/<uuid:organization_id>/subscriptions/",
        SubscriptionAnalyticsView.as_view(),
        name="analytics-subscriptions",
    ),

    path(
        "organizations/<uuid:organization_id>/revenue/",
        RevenueTrendView.as_view(),
        name="analytics-revenue",
    ),

    path(
        "organizations/<uuid:organization_id>/churn/",
        ChurnView.as_view(),
        name="analytics-churn",
    ),

    path(
        "organizations/<uuid:organization_id>/overview/",
        AnalyticsOverviewView.as_view(),
        name="analytics-overview",
    ),
]