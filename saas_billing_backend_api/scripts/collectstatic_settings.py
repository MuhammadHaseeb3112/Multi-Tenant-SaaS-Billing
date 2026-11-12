"""
Settings used ONLY while the Docker image is built, to collect the
static files (Django admin, DRF browsable API) into /app/staticfiles.

Why a separate file: the real settings need the database, Stripe keys
and the application code, none of which exist at that point in the
build. Static files come only from installed packages, so this small
standalone module is enough, and the Docker layer it runs in is reused
until requirements.txt or this file changes. The container then starts
in seconds instead of hashing and compressing ~850 files on every boot.

Keep INSTALLED_APPS and STORAGES in step with config/settings
(apps/core/test_build_settings.py fails if they drift).
"""

SECRET_KEY = "build-time-only-not-used-at-runtime"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]

STATIC_URL = "/static/"
STATIC_ROOT = "/app/staticfiles"

# Same storage as production: hashed file names + gzip/brotli copies,
# served by WhiteNoise.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
