# Deployment Guide

## Quick deploy: whole stack on one server (recommended for the demo)

Any Linux server with Docker (e.g. a 2 GB VPS) and a domain name.

```bash
git clone https://github.com/MuhammadHaseeb3112/Multi-Tenant-SaaS-Billing.git
cd Multi-Tenant-SaaS-Billing
cp deploy/.env.prod.example deploy/.env.prod     # fill in: DOMAIN, secrets, Stripe test keys
docker compose -f deploy/compose.prod.yml --env-file deploy/.env.prod up -d --build
```

1. Point the domain's DNS **A record** to the server IP first — Caddy then
   gets a Let's Encrypt certificate automatically.
2. The web container runs migrations, `collectstatic` and (with
   `SEED_DEMO=true`) `seed_demo` on start. With `DEMO_MODE=true` the login
   page shows one-click demo accounts and Celery Beat resets the demo data
   every night at 03:30 UTC.
3. Stripe → Developers → Webhooks: add `https://<DOMAIN>/api/webhooks/stripe/`
   with the events in section 4 and put its signing secret in
   `STRIPE_WEBHOOK_SECRET`.
4. Check: `https://<DOMAIN>/api/health/ready/` → `{"status": "ok", ...}`.

Topology (`deploy/compose.prod.yml`):

```
Browser ─HTTPS─▶ Caddy ─▶ nginx (React build, /api /admin /static proxy) ─▶ gunicorn (Django)
                                                                              ├─▶ PostgreSQL
                                   Celery worker + beat ◀─ Redis (broker db0, cache db1)
```

Everything is served from **one origin**, so the httpOnly refresh cookie
is first-party (no third-party-cookie problems, no CORS).

The rest of this guide explains the pieces and what to change for a
bigger production setup.

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
| `DJANGO_ALLOWED_HOSTS` | `app.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://app.example.com` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | `https://app.example.com` (only matters if the API is on another origin) |
| `FRONTEND_URL` | `https://app.example.com` (links in invitation emails) |
| `USE_X_FORWARDED_PROTO` | `True` when TLS ends at the proxy and it sends `X-Forwarded-Proto` |
| `NUM_PROXIES` | Number of proxies in front of Django (2 for Caddy + nginx) — real client IP for rate limits |
| `REDIS_CACHE_URL` | `redis://redis:6379/1` — shared cache for rate limits / login lockout (not the Celery DB) |
| `DATABASE_URL` | Alternative to `DB_*` (managed Postgres); add `?sslmode=require` if needed |
| `DB_CONN_MAX_AGE` | Seconds to reuse DB connections (default 60) |
| `WEB_CONCURRENCY` / `GUNICORN_THREADS` | gunicorn workers / threads (default 2×CPU+1 / 2) |
| `JWT_REFRESH_COOKIE_SECURE` | `True` (default in production) |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` / `INFO` |
| `THROTTLE_AUTH_RATE` / `THROTTLE_REGISTER_RATE` | Per-IP limits (default `30/min`, `10/hour`) |
| `LOGIN_MAX_FAILURES_PER_IP_EMAIL` / `_PER_EMAIL` / `LOGIN_LOCKOUT_SECONDS` | Lockout (default 5 / 20 / 900) |
| `DEMO_MODE` / `SEED_DEMO` / `DEMO_PASSWORD` | Public demo only |
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

**Static files:** WhiteNoise serves the collected admin files from
gunicorn (compressed, cache-busted names). `collectstatic` must run on
every deploy (the start script does it).

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
refund.created
refund.updated
charge.refunded
credit_note.created
credit_note.updated
credit_note.voided
```

`invoice.created` is required for usage-overage billing: the overage is
added to the renewal invoice while it is still a draft (Stripe keeps it a
draft for about an hour). If an event is missed, bill the period with
`python manage.py bill_overage --organization <uuid> --start <ISO> --end <ISO>`.

Failed events stay `processed=False` in `WebhookEvent` (admin) with the
error message; Stripe retries automatically and processing is idempotent.
Two simultaneous deliveries of the same event are serialised by a row
lock, so an event is processed exactly once.

## 5. Frontend

```bash
cd saas_billing_frontend
npm ci
npm run build        # output: dist/ (VITE_API_BASE_URL defaults to /api)
```

Recommended: serve `dist/` and proxy `/api`, `/admin`, `/static` to Django
from the same origin (`saas_billing_frontend/Dockerfile` + `nginx.conf` do
exactly this). If the API must live on another domain, set
`VITE_API_BASE_URL=https://api.example.com/api` and
`JWT_REFRESH_COOKIE_SAMESITE=None` — but browsers increasingly block such
third-party cookies, so same-origin is the robust choice.

## 6. Security checklist

- [ ] `DEBUG=False`, strong `DJANGO_SECRET_KEY`, HTTPS everywhere (HSTS is on)
- [ ] `DJANGO_ALLOWED_HOSTS`, CORS and CSRF origins limited to your domains
- [ ] Stripe live keys only in production secrets; webhook signing secret set
- [ ] Database dumps never in the repo or Docker image (`.gitignore`, `.dockerignore`)
- [ ] One `celery-beat` instance
- [ ] `NUM_PROXIES` matches the real proxy chain (else rate limits see the proxy IP)
- [ ] Database backups + restore tested
- [ ] Monitoring for webhook events with `processed=False`

## 7. Scaling further

- **Web:** gunicorn workers are stateless (sessions are JWT, rate-limit
  state is in Redis) — run more `web` replicas behind the load balancer.
- **Database:** add PgBouncer when connections run short; read replicas
  for analytics queries.
- **Workers:** scale `celery` replicas independently; keep one beat.
- **Static/SPA:** put a CDN in front of the nginx container.

## 8. Known limitations / next steps

- Invoice lists are not paginated server-side yet (activity lists are
  bounded to the newest 100–500 rows).
- No end-to-end browser tests in CI (unit/component tests run with Vitest;
  end-to-end flows were verified manually with headless Chrome).
- Email uses the console backend unless SMTP variables are set.
