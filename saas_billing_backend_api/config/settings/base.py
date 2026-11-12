from pathlib import Path

import environ 

from datetime import timedelta
from celery.schedules import crontab

# =============================================================================
# BASE DIRECTORY & ENVIRONMENT
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

environ.Env.read_env(BASE_DIR / ".env")

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_SUCCESS_URL = env("STRIPE_SUCCESS_URL")
STRIPE_CANCEL_URL = env("STRIPE_CANCEL_URL")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")

# Public URL of the React app (used in links inside emails).
FRONTEND_URL = env(
    "FRONTEND_URL",
    default="http://localhost:5173",
).rstrip("/")


# =============================================================================
# SECURITY
# =============================================================================

SECRET_KEY = env("DJANGO_SECRET_KEY")


# =============================================================================
# APPLICATIONS
# =============================================================================

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.tenants",
    "apps.billing",
    "apps.invoices",
    "apps.usage",
    "apps.webhooks",
    "apps.notifications",
    "apps.audit",
    "apps.analytics",
    "apps.core",

    "corsheaders",

]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS



REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Per-IP limits on the public auth endpoints (apps/accounts/security.py).
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH_RATE", default="30/min"),
        "register": env("THROTTLE_REGISTER_RATE", default="10/hour"),
    },
    # Number of trusted reverse proxies in front of Django, so throttles
    # and the login lockout read the real client IP from X-Forwarded-For.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0) or None,
}


# =============================================================================
# CACHE (throttles, login lockout)
# =============================================================================
#
# Redis when REDIS_CACHE_URL is set (production: shared by all gunicorn
# workers). Use a different Redis DB than the Celery broker. Otherwise a
# per-process memory cache (development / tests).

REDIS_CACHE_URL = env("REDIS_CACHE_URL", default="")

if REDIS_CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "KEY_PREFIX": "saas_billing",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# =============================================================================
# LOGIN BRUTE-FORCE PROTECTION
# =============================================================================

LOGIN_MAX_FAILURES_PER_IP_EMAIL = env.int(
    "LOGIN_MAX_FAILURES_PER_IP_EMAIL", default=5
)
LOGIN_MAX_FAILURES_PER_EMAIL = env.int(
    "LOGIN_MAX_FAILURES_PER_EMAIL", default=20
)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=900)


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    # First, so every log line of the request carries its ID.
    "apps.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# URL / APPLICATION CONFIGURATION
# =============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =============================================================================
# DATABASE
# =============================================================================
#
# Database configuration is environment-specific and is defined in:
#
#     development.py
#     production.py
#
# =============================================================================


# =============================================================================
# CUSTOM USER MODEL
# =============================================================================

AUTH_USER_MODEL = "accounts.User"


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

# Password reset links (apps/accounts/account.py) expire after 1 hour.
PASSWORD_RESET_TIMEOUT = 60 * 60

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# EMAIL
# =============================================================================


DEFAULT_FROM_EMAIL = "noreply@saasbilling.local"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# =============================================================================
# SECURITY / COOKIE DEFAULTS
# =============================================================================

SESSION_COOKIE_HTTPONLY = True

# Keep this False so Django's CSRF cookie can be accessed by frontend
# JavaScript when required.
CSRF_COOKIE_HTTPONLY = False

X_FRAME_OPTIONS = "DENY"


# =============================================================================
# LOGGING
# =============================================================================

# LOG_FORMAT=json (production) -> one JSON object per line; default is
# readable text. Every line includes the request ID.
LOG_FORMAT = env("LOG_FORMAT", default="text")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "apps.core.middleware.RequestIDLogFilter",
        },
    },
    "formatters": {
        "text": {
            "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
        },
        "json": {
            "()": "apps.core.logging.JSONFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "json" if LOG_FORMAT == "json" else "text",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        # WeasyPrint/fontTools log every PDF rendering step at INFO.
        "weasyprint": {"level": "WARNING"},
        "fontTools": {"level": "WARNING"},
    },
}




SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# The refresh token lives only in this httpOnly cookie (never in the JSON
# body or localStorage). Path-scoped so it is sent to the auth endpoints
# only. Production: Secure=True; SameSite stays Lax because the frontend
# and API are served from the same site (nginx proxy / Vite dev proxy).
JWT_REFRESH_COOKIE_NAME = "sb_refresh"
JWT_REFRESH_COOKIE_PATH = "/api/auth/"
JWT_REFRESH_COOKIE_SECURE = env.bool("JWT_REFRESH_COOKIE_SECURE", default=False)
JWT_REFRESH_COOKIE_SAMESITE = env("JWT_REFRESH_COOKIE_SAMESITE", default="Lax")



CELERY_BROKER_URL = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6380/0",
)

CELERY_RESULT_BACKEND = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6380/0",
)

# Reliability: a task is acknowledged only after it finished, so a worker
# crash/redeploy re-queues it instead of losing it; one task at a time
# per worker process so long jobs don't hold others hostage.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"


CELERY_BEAT_SCHEDULE = {
    "process-expired-grace-periods": {
        "task": "apps.billing.tasks.process_expired_grace_periods",
        "schedule": crontab(minute=0),
    },

    # Creates due reminder attempts for overdue invoices. Must run
    # before process-dunning-attempts (which sends them).
    "create-due-dunning-attempts": {
        "task": "apps.invoices.tasks.create_due_dunning_attempts",
        "schedule": crontab(minute=2),
    },

    "process-dunning-attempts": {
        "task": "apps.invoices.tasks.process_dunning_attempts",
        "schedule": crontab(minute=5),
    },
}

# Public live demo: nightly reset of the demo data (see seed_demo).
DEMO_MODE = env.bool("DEMO_MODE", default=False)

if DEMO_MODE:
    CELERY_BEAT_SCHEDULE["reset-demo-data"] = {
        "task": "apps.core.tasks.reset_demo_data",
        "schedule": crontab(hour=3, minute=30),
    }

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Needed only when the frontend is on another origin and must send the
# refresh cookie cross-origin (the recommended setup proxies /api instead).
CORS_ALLOW_CREDENTIALS = True