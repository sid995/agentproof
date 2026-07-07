"""Transactional outbox services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.outbox.models import OutboxEvent, OutboxEventStatus
from agentproof_backend.apps.outbox.publishers import publish_outbox_event

MAX_ATTEMPTS = 5
BASE_RETRY_DELAY_SECONDS = 30
MAX_RETRY_DELAY_SECONDS = 15 * 60
LAST_ERROR_MAX_LENGTH = 4_000

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Counts returned by an outbox publish pass."""

    selected: int = 0
    published: int = 0
    failed: int = 0
    retried: int = 0


def enqueue_outbox_event(
    *,
    organization: Organization,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Create an outbox event inside the caller's domain transaction."""

    return OutboxEvent.objects.create(
        organization=organization,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
    )


def publish_pending_outbox_events(*, batch_size: int = 100) -> PublishResult:
    """Lock and publish ready outbox events with at-least-once semantics."""

    now = timezone.now()
    events = _claim_ready_events(batch_size=batch_size, now=now)
    selected = len(events)
    published = 0
    failed = 0
    retried = 0

    for event in events:
        try:
            publish_outbox_event(event)
        except Exception as exc:
            terminal = _mark_publish_failed(event=event, exc=exc)
            failed += 1
            if not terminal:
                retried += 1
        else:
            _mark_published(event=event)
            published += 1

    result = PublishResult(selected=selected, published=published, failed=failed, retried=retried)
    logger.info(
        "outbox_publish_pass_complete",
        selected=result.selected,
        published=result.published,
        failed=result.failed,
        retried=result.retried,
    )
    return result


def recover_stale_outbox_events(*, stale_minutes: int = 15, batch_size: int = 500) -> int:
    """Return abandoned publishing rows to the pending state for retry."""

    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    stale_ids = list(
        OutboxEvent.objects.filter(
            status=OutboxEventStatus.PUBLISHING,
            locked_at__lt=cutoff,
        )
        .order_by("locked_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )

    if not stale_ids:
        logger.info("outbox_stale_recovery_complete", recovered=0)
        return 0

    recovered = OutboxEvent.objects.filter(id__in=stale_ids, status=OutboxEventStatus.PUBLISHING).update(
        status=OutboxEventStatus.PENDING,
        locked_at=None,
        next_attempt_at=timezone.now(),
    )
    logger.info("outbox_stale_recovery_complete", recovered=recovered)
    return recovered


def _claim_ready_events(*, batch_size: int, now: Any) -> list[OutboxEvent]:
    ready_filter = Q(status=OutboxEventStatus.PENDING) & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))

    with transaction.atomic():
        queryset = OutboxEvent.objects.select_for_update(
            skip_locked=connection.features.has_select_for_update_skip_locked
        ).filter(ready_filter)
        events = list(queryset.order_by("created_at", "id")[:batch_size])

        if not events:
            return []

        event_ids = [event.id for event in events]
        OutboxEvent.objects.filter(id__in=event_ids, status=OutboxEventStatus.PENDING).update(
            status=OutboxEventStatus.PUBLISHING,
            locked_at=now,
            last_error="",
        )

    return list(OutboxEvent.objects.filter(id__in=event_ids).order_by("created_at", "id"))


def _mark_published(*, event: OutboxEvent) -> None:
    OutboxEvent.objects.filter(id=event.id).update(
        status=OutboxEventStatus.PUBLISHED,
        published_at=timezone.now(),
        locked_at=None,
        last_error="",
    )


def _mark_publish_failed(*, event: OutboxEvent, exc: Exception) -> bool:
    next_attempt_count = event.attempt_count + 1
    terminal = next_attempt_count >= MAX_ATTEMPTS
    delay_seconds = min(BASE_RETRY_DELAY_SECONDS * (2 ** max(next_attempt_count - 1, 0)), MAX_RETRY_DELAY_SECONDS)
    last_error = f"{type(exc).__name__}: {exc}"[:LAST_ERROR_MAX_LENGTH]

    update_kwargs: dict[str, Any] = {
        "status": OutboxEventStatus.FAILED if terminal else OutboxEventStatus.PENDING,
        "attempt_count": next_attempt_count,
        "locked_at": None,
        "last_error": last_error,
    }

    if terminal:
        update_kwargs["next_attempt_at"] = None
    else:
        update_kwargs["next_attempt_at"] = timezone.now() + timedelta(seconds=delay_seconds)

    OutboxEvent.objects.filter(id=event.id).update(**update_kwargs)
    logger.warning(
        "outbox_publish_failed",
        event_id=str(event.id),
        event_type=event.event_type,
        terminal=terminal,
        attempt_count=next_attempt_count,
        error=last_error,
    )
    return terminal
