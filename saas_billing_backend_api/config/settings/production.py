"""
Production settings for the SaaS Billing project.
"""

from .base import *

import environ


# =============================================================================
# ENVIRONMENT
# =============================================================================

env = environ.Env()


# =============================================================================
# PRODUCTION
# =============================================================================

DEBUG = False


# =============================================================================
# HOSTS
# =============================================================================

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[],
)


# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}


# =============================================================================
# HTTPS / SECURITY
# =============================================================================

SECURE_SSL_REDIRECT = env.bool(
    "SECURE_SSL_REDIRECT",
    default=True,
)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

X_FRAME_OPTIONS = "DENY"


# =============================================================================
# CSRF / TRUSTED ORIGINS
# =============================================================================

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[],
)


# =============================================================================
# CORS (frontend origin)
# =============================================================================
#
# base.py only allows the local Vite dev server. In production set e.g.
# DJANGO_CORS_ALLOWED_ORIGINS=https://app.example.com
# Unset -> keeps the base.py (localhost) list, so local Docker is unchanged.

CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=CORS_ALLOWED_ORIGINS,
)


# =============================================================================
# REVERSE PROXY (TLS terminated by nginx / load balancer)
# =============================================================================
#
# Behind a proxy Django only sees plain HTTP, so SECURE_SSL_REDIRECT would
# redirect forever. Set USE_X_FORWARDED_PROTO=True when the proxy sends
# "X-Forwarded-Proto: https" (and strips it from client requests).

if env.bool("USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# =============================================================================
# EMAIL
# =============================================================================

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = env(
    "EMAIL_HOST",
    default="",
)

EMAIL_PORT = env.int(
    "EMAIL_PORT",
    default=587,
)

EMAIL_USE_TLS = env.bool(
    "EMAIL_USE_TLS",
    default=True,
)

EMAIL_HOST_USER = env(
    "EMAIL_HOST_USER",
    default="",
)

EMAIL_HOST_PASSWORD = env(
    "EMAIL_HOST_PASSWORD",
    default="",
)

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="noreply@saasbilling.local",
)


# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# =============================================================================
# MEDIA FILES
# =============================================================================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"