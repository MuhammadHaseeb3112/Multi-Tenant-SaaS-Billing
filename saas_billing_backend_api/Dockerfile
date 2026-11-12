FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required by WeasyPrint
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user (a compromised process can't modify the
# image or bind privileged ports).
RUN useradd --create-home --uid 10001 app

# Static files (Django admin, DRF) come only from installed packages, so
# they are collected, hashed and compressed HERE, before the application
# code is copied. This layer is reused until requirements.txt or
# scripts/collectstatic_settings.py changes, so a code change does not
# redo it, and the container no longer spends its start-up on it.
COPY scripts/collectstatic_settings.py /tmp/build/collectstatic_settings.py

RUN PYTHONPATH=/tmp/build python -m django collectstatic --noinput \
        --settings=collectstatic_settings \
    && rm -rf /tmp/build

COPY --chown=app:app . .

RUN chmod +x scripts/start-web.sh \
    && mkdir -p staticfiles media \
    && chown app:app /app \
    && chown -R app:app staticfiles media

USER app

EXPOSE 8000

# Web: migrate + gunicorn (gunicorn.conf.py). Celery
# services override the command.
CMD ["./scripts/start-web.sh"]