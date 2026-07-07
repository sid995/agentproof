"""Tests for the transactional outbox."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.ingestion.models import ProcessingStatus, TraceProcessingEvent
from agentproof_backend.apps.outbox.models import OutboxEvent, OutboxEventStatus
from agentproof_backend.apps.outbox.publishers import TRACE_ACCEPTED
from agentproof_backend.apps.outbox.services import (
    MAX_ATTEMPTS,
    enqueue_outbox_event,
    publish_pending_outbox_events,
    recover_stale_outbox_events,
)
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project
from agentproof_backend.apps.projects.services import create_project
from agentproof_backend.apps.telemetry.models import Trace, TraceStatus
from backend.tests.organization_helpers import create_test_organization, create_user

pytestmark = pytest.mark.django_db(transaction=True)

AUDIT_CONTEXT = AuditContext(request_id="phase-8-test", source_ip="127.0.0.1", user_agent="pytest")
STARTED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
USER_COUNTER = count(1)
ORG_COUNTER = count(1)


def make_user() -> User:
    return create_user(email=f"outbox-{next(USER_COUNTER)}@example.com")


def make_project(*, actor: User) -> tuple[Project, Environment]:
    organization, _ = create_test_organization(owner=actor, name=f"Outbox {next(ORG_COUNTER)}")
    result = create_project(
        actor=actor,
        organization=organization,
        name="Outbox Project",
        requested_slug=None,
        description="",
        capture_mode=CaptureMode.FULL,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.project, result.default_environment


def make_trace_processing_event(*, trace_id: str = "trace-outbox") -> TraceProcessingEvent:
    actor = make_user()
    project, environment = make_project(actor=actor)
    trace = Trace.objects.create(
        organization=environment.organization,
        project=project,
        environment=environment,
        external_trace_id=trace_id,
        schema_version="agentproof.v1",
        name="Outbox trace",
        status=TraceStatus.SUCCESS,
        started_at=STARTED_AT,
    )
    return TraceProcessingEvent.objects.create(organization=environment.organization, trace=trace)


def enqueue_trace_event(event: TraceProcessingEvent, payload: dict[str, Any] | None = None) -> OutboxEvent:
    return enqueue_outbox_event(
        organization=event.organization,
        event_type=TRACE_ACCEPTED,
        aggregate_type="trace",
        aggregate_id=event.trace_id,
        payload=payload or {"trace_id": str(event.trace_id), "processing_event_id": str(event.id)},
    )


def enqueue_then_raise(processing_event: TraceProcessingEvent) -> None:
    with transaction.atomic():
        enqueue_trace_event(processing_event)
        raise RuntimeError("rollback")


def test_enqueue_outbox_event_defaults_to_pending() -> None:
    processing_event = make_trace_processing_event()

    outbox_event = enqueue_trace_event(processing_event)

    assert outbox_event.status == OutboxEventStatus.PENDING
    assert outbox_event.attempt_count == 0
    assert outbox_event.organization_id == processing_event.organization_id
    assert outbox_event.payload["processing_event_id"] == str(processing_event.id)


def test_enqueue_outbox_event_rolls_back_with_domain_transaction() -> None:
    processing_event = make_trace_processing_event()

    with pytest.raises(RuntimeError, match="rollback"):
        enqueue_then_raise(processing_event)

    assert not OutboxEvent.objects.filter(aggregate_id=str(processing_event.trace_id)).exists()


def test_publish_pending_outbox_events_marks_event_published() -> None:
    processing_event = make_trace_processing_event()
    outbox_event = enqueue_trace_event(processing_event)

    result = publish_pending_outbox_events(batch_size=10)

    outbox_event.refresh_from_db()
    processing_event.refresh_from_db()
    assert result.selected == 1
    assert result.published == 1
    assert result.failed == 0
    assert outbox_event.status == OutboxEventStatus.PUBLISHED
    assert outbox_event.published_at is not None
    assert processing_event.status == ProcessingStatus.PROCESSED


def test_publish_failure_schedules_retry() -> None:
    processing_event = make_trace_processing_event()
    outbox_event = enqueue_trace_event(processing_event)

    with patch("agentproof_backend.apps.outbox.services.publish_outbox_event", side_effect=RuntimeError("broker down")):
        result = publish_pending_outbox_events(batch_size=10)

    outbox_event.refresh_from_db()
    assert result.selected == 1
    assert result.failed == 1
    assert result.retried == 1
    assert outbox_event.status == OutboxEventStatus.PENDING
    assert outbox_event.attempt_count == 1
    assert outbox_event.next_attempt_at is not None
    assert "broker down" in outbox_event.last_error


def test_publish_failure_marks_terminal_after_max_attempts() -> None:
    processing_event = make_trace_processing_event()
    outbox_event = enqueue_trace_event(processing_event)
    OutboxEvent.objects.filter(id=outbox_event.id).update(attempt_count=MAX_ATTEMPTS - 1)

    with patch("agentproof_backend.apps.outbox.services.publish_outbox_event", side_effect=RuntimeError("bad event")):
        result = publish_pending_outbox_events(batch_size=10)

    outbox_event.refresh_from_db()
    assert result.selected == 1
    assert result.failed == 1
    assert result.retried == 0
    assert outbox_event.status == OutboxEventStatus.FAILED
    assert outbox_event.attempt_count == MAX_ATTEMPTS
    assert outbox_event.next_attempt_at is None


def test_recover_stale_outbox_events_requeues_abandoned_publish() -> None:
    processing_event = make_trace_processing_event()
    outbox_event = enqueue_trace_event(processing_event)
    OutboxEvent.objects.filter(id=outbox_event.id).update(
        status=OutboxEventStatus.PUBLISHING,
        locked_at=timezone.now() - timedelta(minutes=30),
    )

    recovered = recover_stale_outbox_events(stale_minutes=15, batch_size=10)

    outbox_event.refresh_from_db()
    assert recovered == 1
    assert outbox_event.status == OutboxEventStatus.PENDING
    assert outbox_event.locked_at is None
    assert outbox_event.next_attempt_at is not None


def test_crash_after_publish_before_ack_can_republish_idempotently() -> None:
    processing_event = make_trace_processing_event()
    outbox_event = enqueue_trace_event(processing_event)

    with (
        patch("agentproof_backend.apps.outbox.services._mark_published", side_effect=RuntimeError("crash")),
        pytest.raises(RuntimeError, match="crash"),
    ):
        publish_pending_outbox_events(batch_size=10)

    processing_event.refresh_from_db()
    outbox_event.refresh_from_db()
    assert processing_event.status == ProcessingStatus.PROCESSED
    assert outbox_event.status == OutboxEventStatus.PUBLISHING

    OutboxEvent.objects.filter(id=outbox_event.id).update(
        locked_at=timezone.now() - timedelta(minutes=30),
    )
    assert recover_stale_outbox_events(stale_minutes=15, batch_size=10) == 1

    result = publish_pending_outbox_events(batch_size=10)

    processing_event.refresh_from_db()
    outbox_event.refresh_from_db()
    assert result.published == 1
    assert processing_event.status == ProcessingStatus.PROCESSED
    assert outbox_event.status == OutboxEventStatus.PUBLISHED
