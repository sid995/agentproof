"""Trace context manager implementation."""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Mapping
from datetime import datetime
from types import TracebackType
from typing import Any

from agentproof.context import current_span, current_trace
from agentproof.schemas.native import ErrorDetails, SpanEnvelope, TokenUsage, TraceEnvelope
from agentproof.span import SpanContext, duration_ms, utc_now


class TraceContext:
    """Mutable trace builder used as a sync and async context manager."""

    def __init__(
        self,
        *,
        client: Any,
        name: str,
        attributes: Mapping[str, Any] | None = None,
        tags: list[str] | None = None,
        user_identifier: str = "",
        session_identifier: str = "",
    ) -> None:
        self.client = client
        self.name = name
        self.trace_id = uuid.uuid4().hex
        self.started_at = utc_now()
        self.ended_at: datetime | None = None
        self.status = "unknown"
        self.input: dict[str, Any] = {}
        self.output: dict[str, Any] = {}
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.tags = list(tags or [])
        self.error: ErrorDetails | None = None
        self.token_usage: TokenUsage | None = None
        self.user_identifier = user_identifier
        self.session_identifier = session_identifier
        self._spans: list[SpanEnvelope] = []
        self._trace_token: Any | None = None
        self._span_token: Any | None = None
        self._finished = False

    def __enter__(self) -> TraceContext:
        self._trace_token = current_trace.set(self)
        self._span_token = current_span.set(None)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.finish(exc=exc, traceback_obj=tb)
        if self._span_token is not None:
            current_span.reset(self._span_token)
        if self._trace_token is not None:
            current_trace.reset(self._trace_token)

    async def __aenter__(self) -> TraceContext:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.__exit__(exc_type, exc, tb)

    def span(
        self,
        name: str,
        *,
        span_type: str = "custom",
        attributes: Mapping[str, Any] | None = None,
    ) -> SpanContext:
        """Create a child span under the current span, or a root span."""

        parent = current_span.get()
        parent_span_id = parent.span_id if parent is not None else ""
        return SpanContext(
            trace=self,
            name=name,
            span_type=span_type,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )

    def add_span(self, span: SpanContext) -> None:
        """Attach a finished span to this trace."""

        self._spans.append(span.to_envelope())

    def set_input(self, value: Mapping[str, Any]) -> None:
        """Set structured input captured for this trace."""

        self.input = dict(value)

    def set_output(self, value: Mapping[str, Any]) -> None:
        """Set structured output captured for this trace."""

        self.output = dict(value)

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        """Merge structured trace attributes."""

        self.attributes.update(dict(attributes))

    def add_tag(self, tag: str) -> None:
        """Append a trace tag."""

        self.tags.append(tag)

    def set_token_usage(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Set aggregate token metadata for this trace."""

        self.token_usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)

    def finish(self, *, exc: BaseException | None = None, traceback_obj: TracebackType | None = None) -> None:
        """Finalize and enqueue this trace exactly once."""

        if self._finished:
            return

        self.ended_at = utc_now()
        if exc is None:
            self.status = "success"
        else:
            self.status = "error"
            message = "".join(traceback.format_exception(type(exc), exc, traceback_obj)).strip()
            self.error = ErrorDetails(error_type=type(exc).__name__, message=message or str(exc))
        self.client.capture(self.to_envelope())
        self._finished = True

    def to_envelope(self) -> TraceEnvelope:
        """Serialize this trace into the native ingestion envelope."""

        ended_at = self.ended_at or utc_now()
        return TraceEnvelope(
            trace_id=self.trace_id,
            name=self.name,
            started_at=self.started_at,
            status=self.status,
            ended_at=ended_at,
            duration_ms=duration_ms(self.started_at, ended_at),
            input=self.input,
            output=self.output,
            attributes=self.attributes,
            tags=self.tags,
            error=self.error,
            token_usage=self.token_usage,
            user_identifier=self.user_identifier,
            session_identifier=self.session_identifier,
            spans=self._spans,
        )
