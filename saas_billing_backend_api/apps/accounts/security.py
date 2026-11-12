"""
Authentication hardening.

1. Brute-force protection for login
   Failed logins are counted in the cache (Redis in production) per
   (client IP + email) and per email across all IPs. After too many
   failures the login is refused with 429 until the window expires.
   A successful login clears the per-IP counter. Counting *failures*
   (instead of all requests) means a user who logs in normally is never
   affected, while password guessing is stopped quickly.

2. Refresh token in an httpOnly cookie
   The long-lived refresh token is never exposed to JavaScript (so an
   XSS bug cannot steal it). The short-lived access token is returned in
   the response body and kept in memory by the frontend.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle


# =============================================================================
# Client identity
# =============================================================================

def client_ip(request):
    """
    Client IP, honouring REST_FRAMEWORK["NUM_PROXIES"] (X-Forwarded-For)
    exactly like DRF's throttles do.
    """

    return BaseThrottle().get_ident(request)


def _email_hash(email):
    return hashlib.sha256(
        (email or "").strip().lower().encode("utf-8")
    ).hexdigest()[:32]


# =============================================================================
# Failed-login lockout
# =============================================================================

class LoginLockout:
    """
    Cache-backed counters of failed logins.

    Settings (with defaults):
      LOGIN_MAX_FAILURES_PER_IP_EMAIL = 5
      LOGIN_MAX_FAILURES_PER_EMAIL = 20   (distributed guessing)
      LOGIN_LOCKOUT_SECONDS = 900          (15 minutes)
    """

    def __init__(self, request, email):
        self.ip = client_ip(request)
        digest = _email_hash(email)
        self.ip_email_key = f"login-fail:{digest}:{self.ip}"
        self.email_key = f"login-fail:{digest}"

    @property
    def window(self):
        return getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900)

    @property
    def max_ip_email(self):
        return getattr(settings, "LOGIN_MAX_FAILURES_PER_IP_EMAIL", 5)

    @property
    def max_email(self):
        return getattr(settings, "LOGIN_MAX_FAILURES_PER_EMAIL", 20)

    def is_locked(self):
        return (
            (cache.get(self.ip_email_key) or 0) >= self.max_ip_email
            or (cache.get(self.email_key) or 0) >= self.max_email
        )

    def _incr(self, key):
        # add() is atomic (only sets when missing); incr() is atomic on
        # Redis, so concurrent failures are all counted.
        if not cache.add(key, 1, timeout=self.window):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=self.window)

    def register_failure(self):
        self._incr(self.ip_email_key)
        self._incr(self.email_key)

    def reset(self):
        cache.delete(self.ip_email_key)


# =============================================================================
# DRF throttles (coarse per-IP limits on public auth endpoints)
# =============================================================================

class IPRateThrottle(SimpleRateThrottle):
    """Throttle by client IP, whether or not the request is authenticated."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class AuthRateThrottle(IPRateThrottle):
    """Per-IP limit for login / token refresh / invitation accept."""

    scope = "auth"


class RegisterRateThrottle(IPRateThrottle):
    """Per-IP limit for account creation."""

    scope = "register"


# =============================================================================
# Refresh-token cookie
# =============================================================================

def _cookie_settings():
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    return {
        "key": settings.JWT_REFRESH_COOKIE_NAME,
        "max_age": int(lifetime.total_seconds()),
        "httponly": True,
        "secure": settings.JWT_REFRESH_COOKIE_SECURE,
        "samesite": settings.JWT_REFRESH_COOKIE_SAMESITE,
        "path": settings.JWT_REFRESH_COOKIE_PATH,
    }


def set_refresh_cookie(response, refresh_token):
    options = _cookie_settings()
    response.set_cookie(value=str(refresh_token), **options)
    return response


def clear_refresh_cookie(response):
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )
    return response


def get_refresh_cookie(request):
    return request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)


def origin_is_trusted(request):
    """
    Extra CSRF guard for the cookie-authenticated endpoints (refresh,
    logout). Browsers always send Origin on cross-origin POSTs; reject
    origins that are not the API itself or an allowed frontend.
    Requests without Origin (same-origin GET, curl, server-to-server)
    are allowed - they cannot be forged by another website.
    """

    origin = request.META.get("HTTP_ORIGIN")

    if not origin:
        return True

    allowed = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    allowed.update(getattr(settings, "CSRF_TRUSTED_ORIGINS", []))

    own_origin = f"{request.scheme}://{request.get_host()}"

    return origin == own_origin or origin in allowed
