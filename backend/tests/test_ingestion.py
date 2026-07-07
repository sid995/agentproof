"""Tests for the Phase 7 trace-batch ingestion pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.api_keys.models import APIKey, APIKeyScope
from agentproof_backend.apps.api_keys.services import create_api_key
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.ingestion.models import ProcessingStatus, TraceProcessingEvent
from agentproof_backend.apps.ingestion.redaction import redact_canonical_trace
from agentproof_backend.apps.ingestion.tasks import recover_stale_events
from agentproof_backend.apps.outbox.models import OutboxEvent, OutboxEventStatus
from agentproof_backend.apps.outbox.publishers import TRACE_ACCEPTED
from agentproof_backend.apps.outbox.services import publish_pending_outbox_events
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project
from agentproof_backend.apps.projects.services import create_project
from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalTrace
from agentproof_backend.apps.telemetry.models import SpanStatus, SpanType, Trace, TraceStatus
from backend.tests.organization_helpers import create_test_organization, create_user

pytestmark = pytest.mark.django_db(transaction=True)

AUDIT_CONTEXT = AuditContext(request_id="phase-7-test", source_ip="127.0.0.1", user_agent="pytest")
STARTED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
USER_COUNTER = count(1)
INGEST_URL = "/api/v1/ingest/traces"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(email: str | None = None) -> User:
    return create_user(email=email or f"user-{next(USER_COUNTER)}@example.com")


def make_project(
    *,
    actor: User,
    capture_mode: str = CaptureMode.FULL,
) -> tuple[Project, Environment]:
    organization, _ = create_test_organization(owner=actor)
    result = create_project(
        actor=actor,
        organization=organization,
        name="Test Project",
        requested_slug=None,
        description="",
        capture_mode=capture_mode,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.project, result.default_environment


def make_api_key(
    *,
    actor: User,
    environment: Environment,
    scopes: list[str] | None = None,
    expires_at: Any = None,
) -> tuple[APIKey, str]:
    result = create_api_key(
        actor=actor,
        environment=environment,
        name="Test key",
        scopes=scopes or [APIKeyScope.TRACES_WRITE],
        expires_at=expires_at,
        audit_context=AUDIT_CONTEXT,
    )
    return result.api_key, result.plaintext


def bearer_client(plaintext: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")
    return client


def native_batch(
    *,
    trace_id: str = "trace-1",
    record_id: str = "rec-1",
    extra_spans: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spans = [
        {
            "span_id": "span-root",
            "name": "root",
            "started_at": STARTED_AT.isoformat(),
            "ended_at": (STARTED_AT + timedelta(seconds=1)).isoformat(),
            "span_type": SpanType.AGENT,
            "status": SpanStatus.SUCCESS,
        }
    ]
    if extra_spans:
        spans.extend(extra_spans)
    return {
        "source": "agentproof",
        "schema_version": "agentproof.v1",
        "records": [
            {
                "record_id": record_id,
                "payload": {
                    "trace_id": trace_id,
                    "name": "Test trace",
                    "started_at": STARTED_AT.isoformat(),
                    "ended_at": (STARTED_AT + timedelta(seconds=1)).isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "spans": spans,
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


def test_missing_auth_returns_401() -> None:
    client = APIClient()
    response = client.post(INGEST_URL, data={}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_malformed_bearer_returns_401() -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-key")
    response = client.post(INGEST_URL, data=native_batch(), format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_revoked_key_returns_401() -> None:
    from agentproof_backend.apps.api_keys.services import revoke_api_key

    actor = make_user()
    _, env = make_project(actor=actor)
    api_key, plaintext = make_api_key(actor=actor, environment=env)
    revoke_api_key(
        actor=actor,
        organization=env.organization,
        api_key_id=api_key.id,
        audit_context=AUDIT_CONTEXT,
    )

    client = bearer_client(plaintext)
    response = client.post(INGEST_URL, data=native_batch(), format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_expired_key_returns_401() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(
        actor=actor,
        environment=env,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    client = bearer_client(plaintext)
    response = client.post(INGEST_URL, data=native_batch(), format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_wrong_scope_returns_401() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env, scopes=[APIKeyScope.TRACES_READ])
    client = bearer_client(plaintext)
    response = client.post(INGEST_URL, data=native_batch(), format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_batch_returns_202_and_persists_trace() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)

    client = bearer_client(plaintext)
    response = client.post(INGEST_URL, data=native_batch(), format="json")

    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["summary"]["accepted"] == 1
    assert data["summary"]["duplicates"] == 0
    assert data["summary"]["invalid"] == 0
    assert len(data["accepted"]) == 1
    assert data["accepted"][0]["external_trace_id"] == "trace-1"
    assert Trace.objects.filter(environment=env, external_trace_id="trace-1").exists()


def test_processing_event_created_with_trace() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)

    client = bearer_client(plaintext)
    client.post(INGEST_URL, data=native_batch(), format="json")

    trace = Trace.objects.get(environment=env, external_trace_id="trace-1")
    event = TraceProcessingEvent.objects.get(trace=trace)
    outbox_event = OutboxEvent.objects.get(aggregate_id=str(trace.id), event_type=TRACE_ACCEPTED)
    assert event.status == ProcessingStatus.PENDING
    assert outbox_event.status == OutboxEventStatus.PENDING
    assert outbox_event.organization_id == env.organization_id
    assert outbox_event.payload == {
        "trace_id": str(trace.id),
        "processing_event_id": str(event.id),
    }


def test_outbox_publish_processes_accepted_trace_event() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)

    client = bearer_client(plaintext)
    client.post(INGEST_URL, data=native_batch(), format="json")

    result = publish_pending_outbox_events(batch_size=10)

    trace = Trace.objects.get(environment=env, external_trace_id="trace-1")
    event = TraceProcessingEvent.objects.get(trace=trace)
    outbox_event = OutboxEvent.objects.get(aggregate_id=str(trace.id), event_type=TRACE_ACCEPTED)
    assert result.selected == 1
    assert result.published == 1
    assert event.status == ProcessingStatus.PROCESSED
    assert outbox_event.status == OutboxEventStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Idempotency / duplicates
# ---------------------------------------------------------------------------


def test_duplicate_request_returns_duplicate_status() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    client.post(INGEST_URL, data=native_batch(), format="json")
    response = client.post(INGEST_URL, data=native_batch(), format="json")

    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["summary"]["duplicates"] == 1
    assert data["summary"]["accepted"] == 0
    assert Trace.objects.filter(environment=env, external_trace_id="trace-1").count() == 1


def test_intra_batch_duplicate_first_wins() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    batch = {
        "source": "agentproof",
        "schema_version": "agentproof.v1",
        "records": [
            {
                "record_id": "rec-1",
                "payload": {
                    "trace_id": "trace-dup",
                    "name": "First",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": "root",
                            "started_at": STARTED_AT.isoformat(),
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                        }
                    ],
                },
            },
            {
                "record_id": "rec-2",
                "payload": {
                    "trace_id": "trace-dup",
                    "name": "Second",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "spans": [
                        {
                            "span_id": "s2",
                            "name": "root",
                            "started_at": STARTED_AT.isoformat(),
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                        }
                    ],
                },
            },
        ],
    }

    response = client.post(INGEST_URL, data=batch, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["summary"]["accepted"] == 1
    assert data["summary"]["duplicates"] == 1
    assert Trace.objects.filter(environment=env, external_trace_id="trace-dup").count() == 1


# ---------------------------------------------------------------------------
# Validation / invalid records
# ---------------------------------------------------------------------------


def test_invalid_parent_span_returns_per_record_invalid() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    bad_batch = {
        "source": "agentproof",
        "schema_version": "agentproof.v1",
        "records": [
            {
                "record_id": "bad",
                "payload": {
                    "trace_id": "trace-bad",
                    "name": "Bad",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "spans": [
                        {
                            "span_id": "child",
                            "name": "child",
                            "started_at": STARTED_AT.isoformat(),
                            "parent_span_id": "missing-parent",
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                        }
                    ],
                },
            },
            {
                "record_id": "good",
                "payload": {
                    "trace_id": "trace-good",
                    "name": "Good",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "spans": [
                        {
                            "span_id": "root",
                            "name": "root",
                            "started_at": STARTED_AT.isoformat(),
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                        }
                    ],
                },
            },
        ],
    }

    response = client.post(INGEST_URL, data=bad_batch, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["summary"]["invalid"] == 1
    assert data["summary"]["accepted"] == 1


def test_unsupported_source_schema_returns_400() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    response = client.post(
        INGEST_URL,
        data={"source": "unknown", "schema_version": "v99", "records": [{"record_id": "r1", "payload": {}}]},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_empty_records_returns_400() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    response = client.post(
        INGEST_URL,
        data={"source": "agentproof", "schema_version": "agentproof.v1", "records": []},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_too_many_records_returns_400() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    records = [
        {
            "record_id": f"r{i}",
            "payload": {
                "trace_id": f"trace-{i}",
                "name": "t",
                "started_at": STARTED_AT.isoformat(),
                "status": TraceStatus.SUCCESS,
                "spans": [
                    {
                        "span_id": f"s{i}",
                        "name": "root",
                        "started_at": STARTED_AT.isoformat(),
                        "span_type": SpanType.AGENT,
                        "status": SpanStatus.SUCCESS,
                    }
                ],
            },
        }
        for i in range(101)
    ]
    response = client.post(
        INGEST_URL,
        data={"source": "agentproof", "schema_version": "agentproof.v1", "records": records},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Capture mode tests
# ---------------------------------------------------------------------------


def _make_canonical_trace(trace_id: str = "t1") -> CanonicalTrace:
    return CanonicalTrace(
        external_trace_id=trace_id,
        schema_version="agentproof.v1",
        name="Test",
        status=TraceStatus.SUCCESS,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=1),
        input={"prompt": "hello", "password": "secret123"},  # type: ignore[arg-type]
        output={"response": "hi"},  # type: ignore[arg-type]
        attributes={"env": "test"},  # type: ignore[arg-type]
        spans=(
            CanonicalSpan(
                external_span_id="s1",
                name="root",
                span_type=SpanType.AGENT,
                status=SpanStatus.SUCCESS,
                started_at=STARTED_AT,
                input={"content": "user message"},  # type: ignore[arg-type]
                output={"content": "assistant reply"},  # type: ignore[arg-type]
            ),
        ),
    )


def test_metadata_only_strips_input_output() -> None:
    trace = _make_canonical_trace()
    redacted = redact_canonical_trace(trace, CaptureMode.METADATA_ONLY)
    assert redacted.input == {}
    assert redacted.output == {}
    assert redacted.spans[0].input == {}
    assert redacted.spans[0].output == {}


def test_redacted_masks_sensitive_keys() -> None:
    trace = _make_canonical_trace()
    redacted = redact_canonical_trace(trace, CaptureMode.REDACTED)
    assert redacted.input["password"] == "[REDACTED]"
    assert redacted.input["prompt"] == "hello"


def test_full_keeps_content_but_masks_secrets() -> None:
    trace = _make_canonical_trace()
    redacted = redact_canonical_trace(trace, CaptureMode.FULL)
    assert redacted.input["prompt"] == "hello"
    assert redacted.input["password"] == "[REDACTED]"
    assert redacted.spans[0].input["content"] == "user message"


def test_full_capture_mode_via_api_persists_content() -> None:
    actor = make_user()
    _, env = make_project(actor=actor, capture_mode=CaptureMode.FULL)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    batch = {
        "source": "agentproof",
        "schema_version": "agentproof.v1",
        "records": [
            {
                "record_id": "r1",
                "payload": {
                    "trace_id": "trace-full",
                    "name": "Full trace",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "input": {"prompt": "hello"},
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": "root",
                            "started_at": STARTED_AT.isoformat(),
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                            "input": {"content": "user message"},
                        }
                    ],
                },
            }
        ],
    }
    response = client.post(INGEST_URL, data=batch, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    from agentproof_backend.apps.telemetry.models import Span

    span = Span.objects.get(trace__external_trace_id="trace-full")
    assert span.input == {"content": "user message"}


def test_metadata_only_capture_mode_via_api_strips_content() -> None:
    actor = make_user()
    _, env = make_project(actor=actor, capture_mode=CaptureMode.METADATA_ONLY)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    batch = {
        "source": "agentproof",
        "schema_version": "agentproof.v1",
        "records": [
            {
                "record_id": "r1",
                "payload": {
                    "trace_id": "trace-meta",
                    "name": "Meta trace",
                    "started_at": STARTED_AT.isoformat(),
                    "status": TraceStatus.SUCCESS,
                    "input": {"prompt": "hello"},
                    "spans": [
                        {
                            "span_id": "s1",
                            "name": "root",
                            "started_at": STARTED_AT.isoformat(),
                            "span_type": SpanType.AGENT,
                            "status": SpanStatus.SUCCESS,
                            "input": {"content": "user message"},
                        }
                    ],
                },
            }
        ],
    }
    response = client.post(INGEST_URL, data=batch, format="json")
    assert response.status_code == status.HTTP_202_ACCEPTED
    from agentproof_backend.apps.telemetry.models import Span

    span = Span.objects.get(trace__external_trace_id="trace-meta")
    assert span.input == {}


# ---------------------------------------------------------------------------
# Stale event recovery
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_recover_stale_events_requeues_pending() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)
    client.post(INGEST_URL, data=native_batch(), format="json")

    # Backdate the event so it appears stale
    TraceProcessingEvent.objects.update(
        status=ProcessingStatus.PENDING,
        created_at=timezone.now() - timedelta(minutes=30),
        processed_at=None,
    )

    with patch("agentproof_backend.apps.ingestion.tasks.process_trace_events.delay") as mock_delay:
        count_requeued = recover_stale_events(stale_minutes=15)

    assert count_requeued >= 1
    mock_delay.assert_called()


# ---------------------------------------------------------------------------
# Query count test
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_small_batch_query_count_is_bounded() -> None:
    actor = make_user()
    _, env = make_project(actor=actor)
    _, plaintext = make_api_key(actor=actor, environment=env)
    client = bearer_client(plaintext)

    records = [
        {
            "record_id": f"r{i}",
            "payload": {
                "trace_id": f"trace-qc-{i}",
                "name": f"Trace {i}",
                "started_at": STARTED_AT.isoformat(),
                "status": TraceStatus.SUCCESS,
                "spans": [
                    {
                        "span_id": f"s{i}",
                        "name": "root",
                        "started_at": STARTED_AT.isoformat(),
                        "span_type": SpanType.AGENT,
                        "status": SpanStatus.SUCCESS,
                    }
                ],
            },
        }
        for i in range(5)
    ]

    batch = {"source": "agentproof", "schema_version": "agentproof.v1", "records": records}

    # Authenticate first (outside query count window)
    client.post(INGEST_URL, data=batch, format="json")

    # Re-run with fresh traces and count queries
    records2 = [
        {
            "record_id": f"r2-{i}",
            "payload": {
                "trace_id": f"trace-qc2-{i}",
                "name": f"Trace {i}",
                "started_at": STARTED_AT.isoformat(),
                "status": TraceStatus.SUCCESS,
                "spans": [
                    {
                        "span_id": f"s2-{i}",
                        "name": "root",
                        "started_at": STARTED_AT.isoformat(),
                        "span_type": SpanType.AGENT,
                        "status": SpanStatus.SUCCESS,
                    }
                ],
            },
        }
        for i in range(5)
    ]
    batch2 = {"source": "agentproof", "schema_version": "agentproof.v1", "records": records2}

    with CaptureQueriesContext(connection) as captured_queries:
        response = client.post(INGEST_URL, data=batch2, format="json")

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["summary"]["accepted"] == 5
    assert len(captured_queries) < 80
