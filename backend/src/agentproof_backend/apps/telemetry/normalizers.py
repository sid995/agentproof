"""Telemetry normalizers for native and OpenTelemetry style payloads"""

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from agentproof_backend.apps.telemetry.domain import (
    CanonicalSpan,
    CanonicalSpanEvent,
    CanonicalTrace,
    ErrorDetails,
    ModelAttributes,
    TelemetryNormalizer,
    TokenUsage,
)
from agentproof_backend.apps.telemetry.envelopes import SpanEnvelope, TraceEnvelope
from agentproof_backend.apps.telemetry.exceptions import UnsupportedTelemetryPayload
from agentproof_backend.apps.telemetry.models import SpanStatus, SpanType, TraceStatus
from agentproof_backend.apps.telemetry.validation import validate_trace_tree

NATIVE_SCHEMA_VERSION = "agentproof.v1"
OTEL_SCHEMA_VERSION = "otel.v1"


def _datetime_from_unix_nanos(value: object) -> datetime:
    if not isinstance(value, int):
        raise UnsupportedTelemetryPayload("OpenTelemetry timestamp must be integer nanoseconds")
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)


def _string_value(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _mapping_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_value(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _duration_ms(started_at: datetime, ended_at: datetime | None) -> int | None:
    if ended_at is None:
        return None

    return int((ended_at - started_at).total_seconds() * 1000)


def _canonical_event(event: object) -> CanonicalSpanEvent:
    event_map = _mapping_value(event)
    timestamp = event_map.get("timeUnixNano") or event_map.get("occurred_at")
    occurred_at = (
        _datetime_from_unix_nanos(timestamp) if isinstance(timestamp, int) else datetime.fromisoformat(str(timestamp))
    )
    return CanonicalSpanEvent(
        name=_string_value(event_map.get("name"), "event"),
        occurred_at=occurred_at,
        attributes=_mapping_value(event_map.get("attributes", {})),
    )


def _canonical_native_span(span: SpanEnvelope) -> CanonicalSpan:
    token_usage = (
        TokenUsage(
            input_tokens=span.token_usage.input_tokens,
            output_tokens=span.token_usage.output_tokens,
            estimated_cost=span.token_usage.estimated_cost,
        )
        if span.token_usage
        else None
    )
    error = ErrorDetails(error_type=span.error.error_type, message=span.error.message) if span.error else None
    model = (
        ModelAttributes(provider_name=span.model.provider_name, model_name=span.model.model_name)
        if span.model
        else None
    )
    attributes = dict(span.attributes)
    if span.tool is not None:
        attributes.setdefault("tool_name", span.tool.tool_name)
        attributes.setdefault("tool_call_id", span.tool.tool_call_id)

    return CanonicalSpan(
        external_span_id=span.span_id,
        parent_external_span_id=span.parent_span_id,
        name=span.name,
        span_type=span.span_type,
        status=span.status,
        started_at=span.started_at,
        ended_at=span.ended_at,
        duration_ms=span.duration_ms or _duration_ms(span.started_at, span.ended_at),
        attributes=attributes,
        input=span.input,
        output=span.output,
        error=error,
        token_usage=token_usage,
        model=model,
        events=tuple(
            CanonicalSpanEvent(name=event.name, occurred_at=event.occurred_at, attributes=event.attributes)
            for event in span.events
        ),
    )


class NativeAgentProofNormalizer:
    """Normalize native AgentProof schema payloads"""

    def supports(self, schema_version: str, source: str) -> bool:
        return schema_version == NATIVE_SCHEMA_VERSION and source == "agentproof"

    def normalize(self, payload: Mapping[str, Any]) -> list[CanonicalTrace]:
        envelope = TraceEnvelope.model_validate(payload)
        token_usage = (
            TokenUsage(
                input_tokens=envelope.token_usage.input_tokens,
                output_tokens=envelope.token_usage.output_tokens,
                estimated_cost=envelope.token_usage.estimated_cost,
            )
            if envelope.token_usage
            else None
        )
        error = (
            ErrorDetails(error_type=envelope.error.error_type, message=envelope.error.message)
            if envelope.error
            else None
        )

        trace = CanonicalTrace(
            external_trace_id=envelope.trace_id,
            schema_version=envelope.schema_version,
            name=envelope.name,
            status=envelope.status,
            started_at=envelope.started_at,
            ended_at=envelope.ended_at,
            duration_ms=envelope.duration_ms or _duration_ms(envelope.started_at, envelope.ended_at),
            input=envelope.input,
            output=envelope.output,
            attributes=envelope.attributes,
            tags=tuple(envelope.tags),
            error=error,
            token_usage=token_usage,
            user_identifier=envelope.user_identifier,
            session_identifier=envelope.session_identifier,
            spans=tuple(_canonical_native_span(span) for span in envelope.spans),
        )
        validate_trace_tree(trace)
        return [trace]


class OpenTelemetryStyleNormalizer:
    """Normalize a small OpenTelemetry span export into canonical traces"""

    def supports(self, schema_version: str, source: str) -> bool:
        return schema_version == OTEL_SCHEMA_VERSION and source == "opentelemetry"

    def normalize(self, payload: Mapping[str, Any]) -> list[CanonicalTrace]:
        spans_by_trace: dict[str, list[CanonicalSpan]] = {}

        for resource_span in _list_value(payload.get("resourceSpans")):
            resource_map = _mapping_value(resource_span)
            for scope_span in _list_value(resource_map.get("scopeSpans")):
                scope_map = _mapping_value(scope_span)
                for raw_span in _list_value(scope_map.get("spans")):
                    span_map = _mapping_value(raw_span)
                    trace_id = _string_value(span_map.get("traceId"))
                    span_id = _string_value(span_map.get("spanId"))
                    if not trace_id or not span_id:
                        raise UnsupportedTelemetryPayload("OpenTelemetry spans require trace id and span id")

                    started_at = _datetime_from_unix_nanos(span_map.get("startTimeUnixNano"))
                    ended_at = (
                        _datetime_from_unix_nanos(span_map["endTimeUnixNano"])
                        if "endTimeUnixNano" in span_map
                        else None
                    )
                    status_map = _mapping_value(span_map.get("status"))
                    status_code = _string_value(status_map.get("code")).lower()
                    status = SpanStatus.ERROR if status_code == "error" else SpanStatus.UNSET
                    attributes = _mapping_value(span_map.get("attributes"))

                    canonical_span = CanonicalSpan(
                        external_span_id=span_id,
                        parent_external_span_id=_string_value(span_map.get("parentSpanId")),
                        name=_string_value(span_map.get("name"), span_id),
                        span_type=_string_value(attributes.get("agentproof.span_type"), SpanType.CUSTOM),
                        status=status,
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_ms=_duration_ms(started_at, ended_at),
                        attributes=attributes,
                        error=(
                            ErrorDetails(error_type="otel.status", message=_string_value(status_map.get("message")))
                            if status == SpanStatus.ERROR
                            else None
                        ),
                        model=ModelAttributes(
                            provider_name=_string_value(attributes.get("gen_ai.system")),
                            model_name=_string_value(attributes.get("gen_ai.request.model")),
                        ),
                        token_usage=TokenUsage(
                            input_tokens=attributes.get("gen_ai.usage.input_tokens")
                            if isinstance(attributes.get("gen_ai.usage.input_tokens"), int)
                            else None,
                            output_tokens=attributes.get("gen_ai.usage.output_tokens")
                            if isinstance(attributes.get("gen_ai.usage.output_tokens"), int)
                            else None,
                            estimated_cost=Decimal(str(attributes["agentproof.estimated_cost"]))
                            if "agentproof.estimated_cost" in attributes
                            else None,
                        ),
                        events=tuple(_canonical_event(event) for event in _list_value(span_map.get("events"))),
                    )
                    spans_by_trace.setdefault(trace_id, []).append(canonical_span)

        traces: list[CanonicalTrace] = []
        for trace_id, spans in spans_by_trace.items():
            started_at = min(span.started_at for span in spans)
            ended_values = [span.ended_at for span in spans if span.ended_at is not None]
            ended_at = max(ended_values) if ended_values else None
            has_error = any(span.status == SpanStatus.ERROR for span in spans)
            trace = CanonicalTrace(
                external_trace_id=trace_id,
                schema_version=OTEL_SCHEMA_VERSION,
                name=spans[0].name,
                status=TraceStatus.ERROR if has_error else TraceStatus.UNKNOWN,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=_duration_ms(started_at, ended_at),
                spans=tuple(spans),
            )
            validate_trace_tree(trace)
            traces.append(trace)

        if not traces:
            raise UnsupportedTelemetryPayload("OpenTelemetry payload did not contain spans.")

        return traces


NORMALIZERS: tuple[TelemetryNormalizer, ...] = (
    NativeAgentProofNormalizer(),
    OpenTelemetryStyleNormalizer(),
)


def normalize_telemetry(*, schema_version: str, source: str, payload: Mapping[str, Any]) -> list[CanonicalTrace]:
    """Normalize telemetry using the first matching normalizer."""

    for normalizer in NORMALIZERS:
        if normalizer.supports(schema_version, source):
            return normalizer.normalize(payload)

    raise UnsupportedTelemetryPayload(f"Unsupported telemetry payload: {source} {schema_version}")
