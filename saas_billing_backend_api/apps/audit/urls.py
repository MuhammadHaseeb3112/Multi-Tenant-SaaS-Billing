from django.urls import path

from .views import AuditLogListView


urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/",
        AuditLogListView.as_view(),
        name="audit-log-list",
    ),
]