"""Pydantic ingestion envelopes for native AgentProof telemetry."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentproof_backend.apps.telemetry.models import SpanStatus, SpanType, TraceStatus


class FrozenEnvelope(BaseModel):
    """Base immutable envelope config"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TokenUsage(FrozenEnvelope):
    """Token accounting supplied by an SDK or adapter"""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)


class ErrorDetails(FrozenEnvelope):
    """Error details supplied by an SDK or adapter."""

    error_type: str = ""
    message: str = ""


class ModelAttributes(FrozenEnvelope):
    """Model/provider metadata."""

    provider_name: str = ""
    model_name: str = ""


class ToolAttributes(FrozenEnvelope):
    """Tool-call metadata."""

    tool_name: str = ""
    tool_call_id: str = ""


class EventEnvelope(FrozenEnvelope):
    """Native span event payload."""

    name: str
    occurred_at: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanEnvelope(FrozenEnvelope):
    """Native span payload."""

    span_id: str
    name: str
    started_at: datetime
    parent_span_id: str = ""
    span_type: str = SpanType.CUSTOM
    status: str = SpanStatus.UNSET
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
        """Reject ended_at before started_at."""
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be earlier than started_at")
        return self


class TraceEnvelope(FrozenEnvelope):
    """Native trace payload."""

    trace_id: str
    schema_version: str = "agentproof.v1"
    name: str
    started_at: datetime
    status: str = TraceStatus.UNKNOWN
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
        """Reject ended_at before started_at."""
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be earlier than started_at")
        return self
