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
from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalSpanEvent, CanonicalTrace, ModelAttributes
from agentproof_backend.apps.telemetry.exceptions import TelemetryPersistenceError, TelemetryValidationError
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
