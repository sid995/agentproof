"""Operational health endpoints"""

import uuid

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def liveness(_request: HttpRequest) -> JsonResponse:
    """Report whether the Django process is running."""
    return JsonResponse(
        {
            "status": "ok",
            "service": "agentproof-backend",
        }
    )


@require_GET
@never_cache
def readiness(_request: HttpRequest) -> JsonResponse:
    """Report whether required internal infrastructure is reachable"""
    checks: dict[str, str] = {}
    ready = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"failed:{type(exc).__name__}"
        ready = False

    cache_key = f"health-check:{uuid.uuid4().hex}"

    try:
        cache.set(cache_key, "ok", timeout=10)
        cache_value = cache.get(cache_key)
        cache.delete(cache_key)

        if cache_value != "ok":
            raise RuntimeError("Cache value did not round trip correctly")

        checks["cache"] = "ok"

    except Exception as exc:
        checks["cache"] = f"failed:{type(exc).__name__}"
        ready = False

    return JsonResponse(
        {
            "status": "ok" if ready else "unavailable",
            "service": "agentproof-backend",
            "checks": checks,
        },
        status=200 if ready else 503,
    )
