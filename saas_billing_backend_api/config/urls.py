from django.contrib import admin
from django.urls import include, path

from apps.core.health import HealthView, ReadinessView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.tenants.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/webhooks/", include("apps.webhooks.urls")),
    path("api/usage/", include("apps.usage.urls")),
    path("api/v1/", include("apps.usage.product_urls")),
    path("api/invoices/", include("apps.invoices.urls")),
    path("api/analytics/",include("apps.analytics.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path(
        "api/notifications/",
        include("apps.notifications.urls"),
    ),
    

]