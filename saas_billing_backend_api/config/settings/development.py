"""
Development settings for the SaaS Billing project.
"""

from .base import *


# =============================================================================
# DEVELOPMENT
# =============================================================================

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]


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
# EMAIL
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]