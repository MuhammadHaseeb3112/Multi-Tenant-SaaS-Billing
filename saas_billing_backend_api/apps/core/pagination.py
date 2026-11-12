"""
Bounded list sizes. Activity-style lists (audit log, notifications) grow
without limit; returning all rows would get slower forever. They return
the newest `limit` rows (default 100, max 500), set with ?limit=.
"""

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def bounded_limit(request, default=DEFAULT_LIMIT, maximum=MAX_LIMIT):
    try:
        value = int(request.query_params.get("limit", default))
    except (TypeError, ValueError):
        value = default

    return max(1, min(value, maximum))
