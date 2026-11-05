"""
API-key authentication for the metered product API (``/api/v1/``).

Clients send either::

    Authorization: Api-Key sbk_...
    X-API-Key: sbk_...

A valid key authenticates as an anonymous user with ``request.auth``
set to the ``ApiKey``. JWT (dashboard) tokens are not accepted on the
product API, and API keys are not accepted on the dashboard API.
"""

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from rest_framework import authentication, exceptions
from rest_framework.permissions import BasePermission

from .models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Api-Key"

    def get_raw_key(self, request):
        header = authentication.get_authorization_header(request)

        if header:
            parts = header.decode("latin-1").split()

            if parts and parts[0].lower() == self.keyword.lower():
                if len(parts) != 2:
                    raise exceptions.AuthenticationFailed(
                        "Invalid API key header."
                    )
                return parts[1]

        return request.META.get("HTTP_X_API_KEY") or None

    def authenticate(self, request):
        raw_key = self.get_raw_key(request)

        if not raw_key:
            return None

        api_key = (
            ApiKey.objects
            .select_related("organization")
            .filter(key_hash=ApiKey.hash_key(raw_key))
            .first()
        )

        if api_key is None or not api_key.is_active:
            raise exceptions.AuthenticationFailed(
                "Invalid or revoked API key."
            )

        if not api_key.organization.is_active:
            raise exceptions.AuthenticationFailed(
                "Organization is inactive."
            )

        # Cheap single UPDATE, no model save / signals.
        ApiKey.objects.filter(pk=api_key.pk).update(
            last_used_at=timezone.now()
        )

        return AnonymousUser(), api_key

    def authenticate_header(self, request):
        # Makes DRF answer 401 (not 403) when the key is missing.
        return self.keyword


class HasApiKey(BasePermission):
    message = "A valid API key is required."

    def has_permission(self, request, view):
        return isinstance(request.auth, ApiKey)
