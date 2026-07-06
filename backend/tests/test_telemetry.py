"""Tests for canonical telemetry domain behavior."""

from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from django.db import IntegrityError
from hypothesis import given
from hypothesis import strategies as st

from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.projects.models import CaptureMode, Environment
from agentproof_backend.apps.projects.services import create_project
from agentproof_backend.apps.telemetry.domain import (
    CanonicalSpan,
    CanonicalSpanEvent,
    CanonicalTrace,
    ErrorDetails,
    ModelAttributes,
    TokenUsage,
)
from agentproof_backend.apps.telemetry.exceptions import (
    TelemetryPersistenceError,
    TelemetryValidationError,
    UnsupportedTelemetryPayload,
)
from agentproof_backend.apps.telemetry.models import Span, SpanEvent, SpanStatus, SpanType, Trace, TraceStatus
from agentproof_backend.apps.telemetry.normalizers import normalize_telemetry
from agentproof_backend.apps.telemetry.services import persist_canonical_trace
from agentproof_backend.apps.telemetry.validation import validate_trace_tree
from backend.tests.organization_helpers import create_test_organization, create_user

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-six-test",
    source_ip="127.0.0.1",
    user_agent="pytest",
)
STARTED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
USER_COUNTER = count(1)


def create_project_with_default_environment() -> tuple[Environment, object, object]:
    owner = create_user(email=f"owner-{next(USER_COUNTER)}@example.com")
    organization, _membership = create_test_organization(owner=owner)
    result = create_project(
        actor=owner,
        organization=organization,
        name="Support Agent",
        requested_slug=None,
        description="Customer support workflow",
        capture_mode=CaptureMode.REDACTED,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.default_environment, result.project, organization


def canonical_trace(*, trace_id: str = "trace-1", spans: tuple[CanonicalSpan, ...] | None = None) -> CanonicalTrace:
    return CanonicalTrace(
        external_trace_id=trace_id,
        schema_version="agentproof.v1",
        name="Support request",
        status=TraceStatus.SUCCESS,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=2),
        duration_ms=2_000,
        attributes={"source": "test"},
        tags=("support",),
        spans=spans
        or (
            CanonicalSpan(
                external_span_id="root",
                name="Agent run",
                span_type=SpanType.AGENT,
                status=SpanStatus.SUCCESS,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=2),
                duration_ms=2_000,
                events=(
                    CanonicalSpanEvent(
                        name="decision",
                        occurred_at=STARTED_AT + timedelta(seconds=1),
                        attributes={"path": "answer"},
                    ),
                ),
            ),
            CanonicalSpan(
                external_span_id="model",
                parent_external_span_id="root",
                name="Model call",
                span_type=SpanType.MODEL,
                status=SpanStatus.SUCCESS,
                started_at=STARTED_AT + timedelta(milliseconds=200),
                ended_at=STARTED_AT + timedelta(milliseconds=800),
                duration_ms=600,
                model=ModelAttributes(provider_name="openai", model_name="gpt-test"),
            ),
        ),
    )


def test_persist_canonical_trace_with_spans_and_events() -> None:
    environment, project, organization = create_project_with_default_environment()

    trace = persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=canonical_trace(),
    )

    assert Trace.objects.filter(id=trace.id, external_trace_id="trace-1").exists()
    assert Span.objects.filter(trace=trace, external_span_id="root").exists()
    assert Span.objects.filter(trace=trace, external_span_id="model", provider_name="openai").exists()
    assert SpanEvent.objects.filter(span__trace=trace, name="decision").exists()


def test_persist_canonical_trace_stores_metadata_and_usage() -> None:
    environment, project, organization = create_project_with_default_environment()
    canonical = CanonicalTrace(
        external_trace_id="trace-with-metadata",
        schema_version="agentproof.v1",
        name="Metadata trace",
        status=TraceStatus.ERROR,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=1),
        duration_ms=1_000,
        input={"question": "What happened?"},
        output={"answer": "An error happened."},
        attributes={"source": "unit-test"},
        tags=("metadata", "error"),
        error=ErrorDetails(error_type="ValueError", message="Invalid value"),
        token_usage=TokenUsage(input_tokens=10, output_tokens=20),
        user_identifier="user-123",
        session_identifier="session-456",
        spans=(
            CanonicalSpan(
                external_span_id="root",
                name="Root",
                span_type=SpanType.AGENT,
                status=SpanStatus.ERROR,
                started_at=STARTED_AT,
                ended_at=STARTED_AT + timedelta(seconds=1),
                duration_ms=1_000,
                input={"prompt": "hello"},
                output={"completion": "boom"},
                attributes={"operation": "agent"},
                error=ErrorDetails(error_type="ValueError", message="Invalid value"),
                token_usage=TokenUsage(input_tokens=10, output_tokens=20),
                model=ModelAttributes(provider_name="openai", model_name="gpt-test"),
            ),
        ),
    )

    trace = persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=canonical,
    )
    span = Span.objects.get(trace=trace, external_span_id="root")

    assert trace.status == TraceStatus.ERROR
    assert trace.input == {"question": "What happened?"}
    assert trace.output == {"answer": "An error happened."}
    assert trace.attributes == {"source": "unit-test"}
    assert trace.tags == ["metadata", "error"]
    assert trace.error_type == "ValueError"
    assert trace.error_message == "Invalid value"
    assert trace.total_input_tokens == 10
    assert trace.total_output_tokens == 20
    assert trace.user_identifier == "user-123"
    assert trace.session_identifier == "session-456"
    assert span.input == {"prompt": "hello"}
    assert span.output == {"completion": "boom"}
    assert span.attributes == {"operation": "agent"}
    assert span.error_type == "ValueError"
    assert span.error_message == "Invalid value"
    assert span.input_tokens == 10
    assert span.output_tokens == 20
    assert span.provider_name == "openai"
    assert span.model_name == "gpt-test"


def test_persist_rejects_environment_scope_mismatch() -> None:
    environment, _project, organization = create_project_with_default_environment()
    other_environment, other_project, _other_organization = create_project_with_default_environment()

    with pytest.raises(TelemetryPersistenceError):
        persist_canonical_trace(
            organization=organization,
            project=other_project,
            environment=environment,
            canonical_trace=canonical_trace(),
        )

    with pytest.raises(TelemetryPersistenceError):
        persist_canonical_trace(
            organization=organization,
            project=other_project,
            environment=other_environment,
            canonical_trace=canonical_trace(),
        )


def test_duplicate_trace_identity_is_rejected() -> None:
    environment, project, organization = create_project_with_default_environment()
    persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=canonical_trace(),
    )

    with pytest.raises(IntegrityError):
        persist_canonical_trace(
            organization=organization,
            project=project,
            environment=environment,
            canonical_trace=canonical_trace(),
        )


def test_duplicate_span_ids_are_rejected() -> None:
    span = CanonicalSpan(
        external_span_id="same",
        name="Root",
        span_type=SpanType.AGENT,
        status=SpanStatus.SUCCESS,
        started_at=STARTED_AT,
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(span, span)))


def test_missing_parent_is_rejected() -> None:
    span = CanonicalSpan(
        external_span_id="child",
        parent_external_span_id="missing",
        name="Child",
        span_type=SpanType.TOOL,
        status=SpanStatus.SUCCESS,
        started_at=STARTED_AT,
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(span,)))


def test_cycle_is_rejected() -> None:
    first = CanonicalSpan(
        external_span_id="first",
        parent_external_span_id="second",
        name="First",
        span_type=SpanType.CUSTOM,
        status=SpanStatus.UNSET,
        started_at=STARTED_AT,
    )
    second = CanonicalSpan(
        external_span_id="second",
        parent_external_span_id="first",
        name="Second",
        span_type=SpanType.CUSTOM,
        status=SpanStatus.UNSET,
        started_at=STARTED_AT,
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(first, second)))


def test_invalid_timestamps_are_rejected() -> None:
    span = CanonicalSpan(
        external_span_id="bad",
        name="Bad",
        span_type=SpanType.CUSTOM,
        status=SpanStatus.UNSET,
        started_at=STARTED_AT,
        ended_at=STARTED_AT - timedelta(seconds=1),
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(span,)))


def test_child_outside_parent_timing_is_rejected() -> None:
    parent = CanonicalSpan(
        external_span_id="parent",
        name="Parent",
        span_type=SpanType.AGENT,
        status=SpanStatus.SUCCESS,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=1),
    )
    child = CanonicalSpan(
        external_span_id="child",
        parent_external_span_id="parent",
        name="Child",
        span_type=SpanType.TOOL,
        status=SpanStatus.SUCCESS,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=2),
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(parent, child)))


def test_native_payload_normalizes_to_canonical_trace() -> None:
    traces = normalize_telemetry(
        schema_version="agentproof.v1",
        source="agentproof",
        payload={
            "trace_id": "native-trace",
            "schema_version": "agentproof.v1",
            "name": "Native trace",
            "status": "success",
            "started_at": STARTED_AT.isoformat(),
            "spans": [
                {
                    "span_id": "root",
                    "name": "Root",
                    "span_type": "agent",
                    "status": "success",
                    "started_at": STARTED_AT.isoformat(),
                }
            ],
        },
    )

    assert traces[0].external_trace_id == "native-trace"
    assert traces[0].spans[0].external_span_id == "root"


def test_unsupported_payload_metadata_is_rejected() -> None:
    with pytest.raises(UnsupportedTelemetryPayload):
        normalize_telemetry(
            schema_version="unknown.v1",
            source="unknown",
            payload={},
        )


def test_native_payload_with_duplicate_spans_is_rejected() -> None:
    with pytest.raises(TelemetryValidationError):
        normalize_telemetry(
            schema_version="agentproof.v1",
            source="agentproof",
            payload={
                "trace_id": "duplicate-native",
                "schema_version": "agentproof.v1",
                "name": "Duplicate native trace",
                "started_at": STARTED_AT.isoformat(),
                "spans": [
                    {
                        "span_id": "same",
                        "name": "First",
                        "started_at": STARTED_AT.isoformat(),
                    },
                    {
                        "span_id": "same",
                        "name": "Second",
                        "started_at": STARTED_AT.isoformat(),
                    },
                ],
            },
        )


def test_opentelemetry_payload_groups_spans_by_trace() -> None:
    traces = normalize_telemetry(
        schema_version="otel.v1",
        source="opentelemetry",
        payload={
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "otel-trace",
                                    "spanId": "root",
                                    "name": "Root",
                                    "startTimeUnixNano": 1_767_260_000_000_000_000,
                                    "endTimeUnixNano": 1_767_260_001_000_000_000,
                                    "attributes": {"agentproof.span_type": "agent"},
                                },
                                {
                                    "traceId": "otel-trace",
                                    "spanId": "child",
                                    "parentSpanId": "root",
                                    "name": "Child",
                                    "startTimeUnixNano": 1_767_260_000_100_000_000,
                                    "endTimeUnixNano": 1_767_260_000_900_000_000,
                                },
                            ]
                        }
                    ]
                }
            ]
        },
    )

    assert len(traces) == 1
    assert traces[0].external_trace_id == "otel-trace"
    assert {span.external_span_id for span in traces[0].spans} == {"root", "child"}


def test_opentelemetry_payload_maps_error_model_tokens_and_events() -> None:
    traces = normalize_telemetry(
        schema_version="otel.v1",
        source="opentelemetry",
        payload={
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "otel-error-trace",
                                    "spanId": "root",
                                    "name": "Model call",
                                    "startTimeUnixNano": 1_767_260_000_000_000_000,
                                    "endTimeUnixNano": 1_767_260_001_000_000_000,
                                    "status": {"code": "ERROR", "message": "Provider failed"},
                                    "attributes": {
                                        "agentproof.span_type": "model",
                                        "gen_ai.system": "openai",
                                        "gen_ai.request.model": "gpt-test",
                                        "gen_ai.usage.input_tokens": 11,
                                        "gen_ai.usage.output_tokens": 22,
                                    },
                                    "events": [
                                        {
                                            "name": "exception",
                                            "timeUnixNano": 1_767_260_000_500_000_000,
                                            "attributes": {"exception.type": "ValueError"},
                                        }
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ]
        },
    )

    span = traces[0].spans[0]

    assert traces[0].status == TraceStatus.ERROR
    assert span.span_type == SpanType.MODEL
    assert span.status == SpanStatus.ERROR
    assert span.error is not None
    assert span.error.message == "Provider failed"
    assert span.model is not None
    assert span.model.provider_name == "openai"
    assert span.model.model_name == "gpt-test"
    assert span.token_usage is not None
    assert span.token_usage.input_tokens == 11
    assert span.token_usage.output_tokens == 22
    assert span.events[0].name == "exception"
    assert span.events[0].attributes == {"exception.type": "ValueError"}


def test_empty_opentelemetry_payload_is_rejected() -> None:
    with pytest.raises(UnsupportedTelemetryPayload):
        normalize_telemetry(
            schema_version="otel.v1",
            source="opentelemetry",
            payload={"resourceSpans": []},
        )


@given(st.lists(st.text(min_size=1, max_size=12), min_size=1, max_size=20, unique=True))
def test_generated_span_trees_validate(span_ids: list[str]) -> None:
    spans: list[CanonicalSpan] = []
    for index, span_id in enumerate(span_ids):
        spans.append(
            CanonicalSpan(
                external_span_id=span_id,
                parent_external_span_id="" if index == 0 else span_ids[index - 1],
                name=f"Span {index}",
                span_type=SpanType.CUSTOM,
                status=SpanStatus.UNSET,
                started_at=STARTED_AT + timedelta(milliseconds=index),
                ended_at=STARTED_AT + timedelta(seconds=1),
                duration_ms=1,
            )
        )

    root_ids = validate_trace_tree(canonical_trace(spans=tuple(spans)))

    assert root_ids == (span_ids[0],)


@given(st.lists(st.text(min_size=1, max_size=12), min_size=1, max_size=20, unique=True))
def test_generated_native_payloads_normalize_to_valid_span_trees(span_ids: list[str]) -> None:
    spans = [
        {
            "span_id": span_id,
            "parent_span_id": "" if index == 0 else span_ids[index - 1],
            "name": f"Span {index}",
            "span_type": "custom",
            "status": "unset",
            "started_at": (STARTED_AT + timedelta(milliseconds=index)).isoformat(),
            "ended_at": (STARTED_AT + timedelta(seconds=1)).isoformat(),
        }
        for index, span_id in enumerate(span_ids)
    ]

    traces = normalize_telemetry(
        schema_version="agentproof.v1",
        source="agentproof",
        payload={
            "trace_id": "generated-trace",
            "schema_version": "agentproof.v1",
            "name": "Generated trace",
            "status": "unknown",
            "started_at": STARTED_AT.isoformat(),
            "ended_at": (STARTED_AT + timedelta(seconds=1)).isoformat(),
            "spans": spans,
        },
    )

    trace = traces[0]
    root_ids = validate_trace_tree(trace)

    assert root_ids == (span_ids[0],)
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
    assert all(span.duration_ms is not None and span.duration_ms >= 0 for span in trace.spans)


@given(st.text(min_size=1, max_size=12))
def test_generated_duplicate_span_identifier_is_rejected(span_id: str) -> None:
    first = CanonicalSpan(
        external_span_id=span_id,
        name="First",
        span_type=SpanType.CUSTOM,
        status=SpanStatus.UNSET,
        started_at=STARTED_AT,
    )
    second = CanonicalSpan(
        external_span_id=span_id,
        name="Second",
        span_type=SpanType.CUSTOM,
        status=SpanStatus.UNSET,
        started_at=STARTED_AT,
    )

    with pytest.raises(TelemetryValidationError):
        validate_trace_tree(canonical_trace(spans=(first, second)))
