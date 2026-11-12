"""
Request ID: every request gets an ID (taken from the incoming
X-Request-ID header when a proxy already set one, else generated). It is
returned in the X-Request-ID response header and added to every log line
of that request, so one user-reported error can be traced end to end.
"""

import contextvars
import logging
import re
import uuid


request_id_var = contextvars.ContextVar("request_id", default="-")

# Accept only sane incoming IDs (no log injection, bounded length).
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIDMiddleware:
    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.header, "")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex

        token = request_id_var.set(request_id)
        request.request_id = request_id

        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)

        response["X-Request-ID"] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    """Adds `request_id` to every log record."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True
