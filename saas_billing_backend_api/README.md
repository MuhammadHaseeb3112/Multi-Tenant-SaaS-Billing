# SaaS Billing — Backend API

Django 6 + DRF + PostgreSQL + Celery + Stripe.
See the [project README](../README.md) for features, architecture and setup,
and [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) for production.

```bash
cp .env.example .env                       # fill in values
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web pytest -q
```

Useful commands:

| Command | Purpose |
|---|---|
| `python manage.py backfill_payments [--dry-run]` | Import Stripe invoices paid before the Payment ledger existed |
| `python manage.py bill_overage --organization <uuid> --start <ISO> --end <ISO> [--dry-run]` | Bill a period's usage overage manually (missed webhook) |

Settings: `config.settings.development` (local) / `config.settings.production`
(Docker). Celery app: `config.celery`.
