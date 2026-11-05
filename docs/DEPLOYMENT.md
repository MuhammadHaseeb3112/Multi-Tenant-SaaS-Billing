# Deployment Guide

Production checklist for SaaS Billing. The included `compose.yml` already
runs the production settings (`config.settings.production`, gunicorn,
`DEBUG=False`) on a single host; this guide covers what to add for a
real, public deployment.

## 1. Services

| Service | Command | Notes |
|---|---|---|
| web | `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3` | Behind nginx / a load balancer with HTTPS |
| celery | `celery -A config.celery worker` | Emails, dunning reminders, grace-period downgrades |
| celery-beat | `celery -A config.celery beat` | **Exactly one** instance (otherwise jobs run twice) |
| postgres | PostgreSQL 16+ | Managed database recommended, daily backups |
| redis | Redis 7 | Celery broker / results |
| frontend | static files from `npm run build` | Any static host (nginx, Netlify, Vercel, S3 + CDN) |

`stripe-cli` in `compose.yml` is for **development only** (test-mode
forwarding). In production Stripe calls your public webhook URL directly.

## 2. Environment variables (backend)

Start from `saas_billing_backend_api/.env.example`. In production:

| Variable | Production value |
|---|---|
| `DJANGO_SECRET_KEY` | Long random string (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `DJANGO_ALLOWED_HOSTS` | `api.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://app.example.com,https://api.example.com` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | `https://app.example.com` (the frontend origin) |
| `FRONTEND_URL` | `https://app.example.com` (links in invitation emails) |
| `USE_X_FORWARDED_PROTO` | `True` when TLS ends at the proxy and it sends `X-Forwarded-Proto` |
| `SECURE_SSL_REDIRECT` | `True` (compose defaults to `False` for local HTTP) |
| `DB_*`, `REDIS_URL` | Your managed Postgres / Redis |
| `STRIPE_SECRET_KEY` | `sk_live_...` (restricted key recommended) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret of the **live** webhook endpoint (step 4) |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` | `https://app.example.com/subscriptions?...` |
| `EMAIL_*` | Real SMTP provider (`EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`) |

Never commit `.env`. Keep secrets in the host's secret manager.

## 3. Release steps

```bash
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d
docker compose run --rm web python manage.py createsuperuser   # first deploy only
```

**Static files:** with `DEBUG=False`, gunicorn does not serve `/static/`
(Django admin CSS). Serve `staticfiles/` from nginx (`location /static/`)
or add WhiteNoise.

Then in Django admin:
1. Create plans `FREE`, `PRO`, `ENTERPRISE` with their **live** Stripe
   product / price IDs, `api_request_limit`, and optionally
   `overage_price_per_1000` + `max_overage_requests` (FREE: overage 0).
2. Give platform admins `is_staff` to see `/api/analytics/platform/overview/`.

One-time data import after enabling the Payment ledger:
`python manage.py backfill_payments --dry-run`, then without `--dry-run`.

## 4. Stripe webhook (live)

Dashboard → Developers → Webhooks → Add endpoint:
`https://api.example.com/api/webhooks/stripe/`

Subscribe to:

```
checkout.session.completed
checkout.session.async_payment_succeeded
invoice.created
invoice.paid
invoice.payment_succeeded
invoice.payment_failed
customer.subscription.updated
customer.subscription.deleted
```

`invoice.created` is required for usage-overage billing: the overage is
added to the renewal invoice while it is still a draft (Stripe keeps it a
draft for about an hour). If an event is missed, bill the period with
`python manage.py bill_overage --organization <uuid> --start <ISO> --end <ISO>`.

Failed events stay `processed=False` in `WebhookEvent` (admin) with the
error message; Stripe retries automatically and processing is idempotent.

## 5. Frontend

```bash
cd saas_billing_frontend
npm ci
VITE_API_BASE_URL=https://api.example.com/api npm run build   # output: dist/
```

Serve `dist/` with an SPA fallback (all unknown paths → `index.html`), e.g.
nginx `try_files $uri /index.html;`.

## 6. Security checklist

- [ ] `DEBUG=False`, strong `DJANGO_SECRET_KEY`, HTTPS everywhere (HSTS is on)
- [ ] `DJANGO_ALLOWED_HOSTS`, CORS and CSRF origins limited to your domains
- [ ] Stripe live keys only in production secrets; webhook signing secret set
- [ ] Database dumps never in the repo or Docker image (`.gitignore`, `.dockerignore`)
- [ ] One `celery-beat` instance
- [ ] Database backups + restore tested
- [ ] Monitoring for webhook events with `processed=False`

## 7. Known limitations / next steps

- No login rate limiting yet (add DRF throttling or a proxy limit on
  `/api/auth/login/`).
- JWT access/refresh tokens are kept in `localStorage`; consider httpOnly
  cookies for the refresh token.
- Refunds / credit notes (`charge.refunded`) are not processed yet.
- Concurrent duplicate deliveries of the same webhook event are not row-locked.
