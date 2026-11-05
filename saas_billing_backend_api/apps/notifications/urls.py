from django.urls import path

from .views import (
    NotificationListView,
    UnreadNotificationCountView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
)


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/unread-count/",
        UnreadNotificationCountView.as_view(),
        name="notification-unread-count",
    ),

    path(
        "organizations/<uuid:organization_id>/read-all/",
        MarkAllNotificationsReadView.as_view(),
        name="notification-mark-all-read",
    ),

    path(
        "organizations/<uuid:organization_id>/<uuid:notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="notification-mark-read",
    ),

    path(
        "organizations/<uuid:organization_id>/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
]