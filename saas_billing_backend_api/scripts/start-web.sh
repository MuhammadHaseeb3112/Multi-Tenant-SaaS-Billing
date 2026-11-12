#!/bin/sh
# Container entrypoint for the web service: apply migrations,
# optionally seed the demo, then start gunicorn (settings in
# gunicorn.conf.py).
set -e

python manage.py migrate --noinput

# Static files are collected when the image is built (see Dockerfile),
# so the container is ready in seconds. Only if that step was skipped
# (no manifest in the image) are they collected here, as before.
if [ ! -f staticfiles/staticfiles.json ]; then
    python manage.py collectstatic --noinput
fi

if [ "${SEED_DEMO:-false}" = "true" ]; then
    python manage.py seed_demo
fi

exec gunicorn config.wsgi:application
