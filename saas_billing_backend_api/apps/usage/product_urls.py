"""
Product API (``/api/v1/``) - authenticated with API keys, metered.
"""

from django.urls import path

from .views import ProductUsageView, TextAnalyzeView


urlpatterns = [
    path(
        "text/analyze/",
        TextAnalyzeView.as_view(),
        name="product-text-analyze",
    ),
    path(
        "usage/",
        ProductUsageView.as_view(),
        name="product-usage",
    ),
]
