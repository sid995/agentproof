"""Frozen canonical telemetry domain objects and protocols."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token accounting"""

    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ErrorDetails:
    """Error metadata"""

    error_type: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class ModelAttributes:
    """Provider and model metadata for model spans"""

    provider_name: str = ""
    model_name: str = ""


@dataclass(frozen=True, slots=True)
class ToolAttributes:
    """Tool metadata for tool calls"""

    tool_name: str = ""
    tool_call_id: str = ""


@dataclass(frozen=True, slots=True)
class CanonicalSpanEvent:
    """Point in time span event"""

    name: str
    occurred_at: datetime
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CanonicalSpan:
    """Span representation independent of the source provider"""

    external_span_id: str
    name: str
    span_type: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    parent_external_span_id: str = ""
    duration_ms: int | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    input: Mapping[str, Any] = field(default_factory=dict)
    output: Mapping[str, Any] = field(default_factory=dict)
    error: ErrorDetails | None = None
    token_usage: TokenUsage | None = None
    model: ModelAttributes | None = None
    events: tuple[CanonicalSpanEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalTrace:
    """Canonical trace representation independent of source provider."""

    name: str
    status: str
    external_trace_id: str
    schema_version: str
    started_at: datetime
    spans: tuple[CanonicalSpan, ...]
    ended_at: datetime | None = None
    duration_ms: int | None = None
    input: Mapping[str, Any] = field(default_factory=dict)
    output: Mapping[str, Any] = field(default_factory=dict)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    error: ErrorDetails | None = None
    token_usage: TokenUsage | None = None
    user_identifier: str = ""
    session_identifier: str = ""


class TelemetryNormalizer(Protocol):
    """Normalize source-specific payloads into canonical traces."""

    def supports(self, schema_version: str, source: str) -> bool:
        """Return whether this normalizer supports the payload metadata."""

    def normalize(self, payload: Mapping[str, Any]) -> list[CanonicalTrace]:
        """Normalize a payload into canonical traces."""
