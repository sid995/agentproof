"""Native AgentProof v1 ingestion envelopes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenEnvelope(BaseModel):
    """Base immutable schema config."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def validate_datetime_order(*, started_at: datetime, ended_at: datetime | None) -> None:
    """Reject invalid ordering and mixed timezone-awareness."""

    if ended_at is None:
        return

    try:
        ends_before_start = ended_at < started_at
    except TypeError as exc:
        raise ValueError("started_at and ended_at must both be timezone-aware or both be timezone-naive") from exc

    if ends_before_start:
        raise ValueError("ended_at cannot be earlier than started_at")


class TokenUsage(FrozenEnvelope):
    """Token accounting supplied by instrumentation."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)


class ErrorDetails(FrozenEnvelope):
    """Error details captured from user code."""

    error_type: str = ""
    message: str = ""


class ModelAttributes(FrozenEnvelope):
    """Provider and model metadata."""

    provider_name: str = ""
    model_name: str = ""


class ToolAttributes(FrozenEnvelope):
    """Tool-call metadata."""

    tool_name: str = ""
    tool_call_id: str = ""


class EventEnvelope(FrozenEnvelope):
    """Point-in-time span event."""

    name: str
    occurred_at: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanEnvelope(FrozenEnvelope):
    """Native AgentProof span payload."""

    span_id: str
    name: str
    started_at: datetime
    parent_span_id: str = ""
    span_type: str = "custom"
    status: str = "unset"
    ended_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetails | None = None
    token_usage: TokenUsage | None = None
    model: ModelAttributes | None = None
    tool: ToolAttributes | None = None
    events: list[EventEnvelope] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        """Reject spans that end before they start."""

        validate_datetime_order(started_at=self.started_at, ended_at=self.ended_at)
        return self


class TraceEnvelope(FrozenEnvelope):
    """Native AgentProof trace payload."""

    trace_id: str
    schema_version: str = "agentproof.v1"
    name: str
    started_at: datetime
    status: str = "unknown"
    ended_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    error: ErrorDetails | None = None
    token_usage: TokenUsage | None = None
    user_identifier: str = ""
    session_identifier: str = ""
    spans: list[SpanEnvelope]

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        """Reject traces that end before they start."""

        validate_datetime_order(started_at=self.started_at, ended_at=self.ended_at)
        return self


class IngestRecord(FrozenEnvelope):
    """One trace record in the ingestion batch."""

    record_id: str = ""
    payload: TraceEnvelope


class BatchEnvelope(FrozenEnvelope):
    """Trace ingestion batch sent to AgentProof."""

    source: str = "agentproof"
    schema_version: str = "agentproof.v1"
    records: list[IngestRecord]
