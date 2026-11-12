"""
Gunicorn settings (picked up automatically from the working directory).

Workers: WEB_CONCURRENCY if set (platforms like Render/Heroku set it to
match the instance size), else 2 x CPU + 1. Threads let each worker
overlap I/O (DB, Stripe calls).
"""

import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

workers = int(
    os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1)
)
threads = int(os.environ.get("GUNICORN_THREADS", "2"))

# Stripe/PDF requests can be slow; anything longer is a bug.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

# Recycle workers now and then (protects against slow memory leaks).
max_requests = 1000
max_requests_jitter = 100

# Logs to stdout/stderr for the container platform.
accesslog = "-"
errorlog = "-"

# Trust X-Forwarded-* from the reverse proxy in front (nginx / platform).
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")
