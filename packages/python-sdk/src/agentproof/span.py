"""Span context manager implementation."""

from __future__ import annotations

import time
import traceback
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any

from agentproof.context import current_span
from agentproof.schemas.native import (
    ErrorDetails,
    EventEnvelope,
    ModelAttributes,
    SpanEnvelope,
    TokenUsage,
    ToolAttributes,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


def duration_ms(started_at: datetime, ended_at: datetime) -> int:
    """Return whole milliseconds between two timestamps."""

    return int((ended_at - started_at).total_seconds() * 1000)


class SpanContext:
    """Mutable span builder used as a sync and async context manager."""

    def __init__(
        self,
        *,
        trace: Any,
        name: str,
        span_type: str = "custom",
        parent_span_id: str = "",
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.trace = trace
        self.name = name
        self.span_type = span_type
        self.span_id = uuid.uuid4().hex
        self.parent_span_id = parent_span_id
        self.started_at = utc_now()
        self.ended_at: datetime | None = None
        self.status = "unset"
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.input: dict[str, Any] = {}
        self.output: dict[str, Any] = {}
        self.error: ErrorDetails | None = None
        self.token_usage: TokenUsage | None = None
        self.model: ModelAttributes | None = None
        self.tool: ToolAttributes | None = None
        self.events: list[EventEnvelope] = []
        self._token: Any | None = None
        self._finished = False

    def __enter__(self) -> SpanContext:
        self._token = current_span.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.finish(exc=exc, traceback_obj=tb)
        if self._token is not None:
            current_span.reset(self._token)

    async def __aenter__(self) -> SpanContext:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.__exit__(exc_type, exc, tb)

    def set_input(self, value: Mapping[str, Any]) -> None:
        """Set structured input captured for this span."""

        self.input = dict(value)

    def set_output(self, value: Mapping[str, Any]) -> None:
        """Set structured output captured for this span."""

        self.output = dict(value)

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        """Merge structured span attributes."""

        self.attributes.update(dict(attributes))

    def set_token_usage(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost: Decimal | str | int | float | None = None,
    ) -> None:
        """Set model token usage metadata."""

        cost = Decimal(str(estimated_cost)) if estimated_cost is not None else None
        self.token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
        )

    def set_model(self, *, provider_name: str = "", model_name: str = "") -> None:
        """Set model/provider metadata."""

        self.model = ModelAttributes(provider_name=provider_name, model_name=model_name)

    def set_tool(self, *, tool_name: str = "", tool_call_id: str = "") -> None:
        """Set tool-call metadata."""

        self.tool = ToolAttributes(tool_name=tool_name, tool_call_id=tool_call_id)

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        """Append a point-in-time event to this span."""

        self.events.append(EventEnvelope(name=name, occurred_at=utc_now(), attributes=dict(attributes or {})))

    def finish(self, *, exc: BaseException | None = None, traceback_obj: TracebackType | None = None) -> None:
        """Finalize the span and attach it to its trace exactly once."""

        if self._finished:
            return

        ended_at = utc_now()
        self.ended_at = ended_at
        if exc is None:
            self.status = "success"
        else:
            self.status = "error"
            message = "".join(traceback.format_exception(type(exc), exc, traceback_obj)).strip()
            self.error = ErrorDetails(error_type=type(exc).__name__, message=message or str(exc))
        self.trace.add_span(self)
        self._finished = True

    def to_envelope(self) -> SpanEnvelope:
        """Serialize this span into the native ingestion envelope."""

        ended_at = self.ended_at or utc_now()
        return SpanEnvelope(
            span_id=self.span_id,
            name=self.name,
            started_at=self.started_at,
            parent_span_id=self.parent_span_id,
            span_type=self.span_type,
            status=self.status,
            ended_at=ended_at,
            duration_ms=duration_ms(self.started_at, ended_at),
            attributes=self.attributes,
            input=self.input,
            output=self.output,
            error=self.error,
            token_usage=self.token_usage,
            model=self.model,
            tool=self.tool,
            events=self.events,
        )

    def elapsed_seconds(self) -> float | int:
        """Return elapsed wall-clock seconds for callers that need live timing."""

        return time.monotonic()
