"""Celery tasks for ingestion processing"""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(name="ingestion.process_trace_events", max_retries=3)
def process_trace_events(event_id: str) -> None:
    """Mark a TraceProcessingEvent as processed.

    Aggregate computation is a placeholder for later phases.
    """
    from agentproof_backend.apps.ingestion.models import ProcessingStatus, TraceProcessingEvent

    updated = TraceProcessingEvent.objects.filter(
        id=event_id,
        status=ProcessingStatus.PENDING,
    ).update(
        status=ProcessingStatus.PROCESSED,
        processed_at=timezone.now(),
    )

    if updated == 0:
        # Already processed or missing -> idempotent  -> do nothing
        return


@shared_task(name="ingestion.recover_stale_events")
def recover_stale_events(stale_minutes: int = 15) -> int:
    """Requeue pending events that have not been processed within the stale window"""
    from agentproof_backend.apps.ingestion.models import ProcessingStatus, TraceProcessingEvent

    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    stale_ids = list(
        TraceProcessingEvent.objects.filter(
            status=ProcessingStatus.PENDING,
            created_at__lt=cutoff,
        ).values_list("id", flat=True)[:500]
    )

    for event_id in stale_ids:
        process_trace_events.delay(str(event_id))

    return len(stale_ids)
