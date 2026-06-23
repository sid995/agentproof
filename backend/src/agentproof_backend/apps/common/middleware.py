"""Application Middleware"""

import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

import structlog
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpRequest, HttpResponse
from structlog.contextvars import bind_contextvars, clear_contextvars

SyncGetResponse = Callable[[HttpRequest], HttpResponse]
AsyncGetResponse = Callable[[HttpRequest], Awaitable[HttpResponse]]
GetResponse = SyncGetResponse | AsyncGetResponse

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")

logger = structlog.get_logger(__name__)


class RequestIDMiddleware:
    """Attach a correlation identifier to every request and response."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response
        self.is_async = iscoroutinefunction(get_response)

        if self.is_async:
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> HttpResponse | Awaitable[HttpResponse]:
        if self.is_async:
            return self._async_call(request)

        return self._sync_call(request)

    def _sync_call(self, request: HttpRequest) -> HttpResponse:
        request_id = self._resolve_request_id(request)
        cast(Any, request).request_id = request_id
        started_at = time.perf_counter()

        clear_contextvars()
        bind_contextvars(request_id=request_id)

        get_response = cast(SyncGetResponse, self.get_response)

        try:
            response = get_response(request)
            response.headers[REQUEST_ID_HEADER] = request_id

            logger.info(
                "http_request_completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round(
                    (time.perf_counter() - started_at) * 1_000,
                    2,
                ),
            )

            return response

        except Exception:
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.path,
                duration_ms=round(
                    time.perf_counter() - started_at * 1_000,
                    2,
                ),
            )
            raise
        finally:
            clear_contextvars()

    async def _async_call(self, request: HttpRequest) -> HttpResponse:
        request_id = self._resolve_request_id(request)
        cast(Any, request).request_id = request_id
        started_at = time.perf_counter()

        clear_contextvars()
        bind_contextvars(request_id=request_id)

        get_response = cast(AsyncGetResponse, self.get_response)

        try:
            response = await get_response(request)
            response.headers[REQUEST_ID_HEADER] = request_id

            logger.info(
                "http_request_completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round(
                    (time.perf_counter() - started_at) * 1_000,
                    2,
                ),
            )

            return response
        except Exception:
            logger.exception(
                "http_request_failed",
                method=request.method,
                path=request.path,
                duration_ms=round(
                    (time.perf_counter() - started_at) * 1_000,
                    2,
                ),
            )
            raise
        finally:
            clear_contextvars()

    @staticmethod
    def _resolve_request_id(request: HttpRequest) -> str:
        supplied_request_id = request.headers.get(
            REQUEST_ID_HEADER,
            "",
        ).strip()

        if REQUEST_ID_PATTERN.fullmatch(supplied_request_id):
            return supplied_request_id

        return uuid.uuid4().hex
