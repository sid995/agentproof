"""REST API exception handling"""

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """Convert DRF exceptions into a consistent error envelope"""
    response = exception_handler(exc, context)

    if response is None:
        return None

    response.data = {
        "error": {
            "status_code": response.status_code,
            "details": response.data,
        }
    }

    return response
