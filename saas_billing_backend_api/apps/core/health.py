"""
Health endpoints for load balancers / container orchestrators.

  GET /api/health/        liveness: the process answers (no I/O)
  GET /api/health/ready/  readiness: database and cache reachable

Unauthenticated and not throttled; they expose no data.
"""

import logging

from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger(__name__)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ReadinessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        checks = {}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001 - report, don't crash
            logger.exception("Readiness: database check failed")
            checks["database"] = "error"

        try:
            cache.set("health:ping", "1", timeout=5)
            checks["cache"] = "ok" if cache.get("health:ping") == "1" else "error"
        except Exception:  # noqa: BLE001
            logger.exception("Readiness: cache check failed")
            checks["cache"] = "error"

        healthy = all(value == "ok" for value in checks.values())

        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=(
                status.HTTP_200_OK
                if healthy
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )
