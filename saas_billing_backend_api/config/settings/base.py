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
}


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}




SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}



CELERY_BROKER_URL = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6380/0",
)

CELERY_RESULT_BACKEND = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6380/0",
)

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

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]