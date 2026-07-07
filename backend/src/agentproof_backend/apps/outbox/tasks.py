"""Celery tasks for the transactional outbox."""

from celery import shared_task


@shared_task(name="outbox.publish_pending_events")
def publish_pending_events(batch_size: int = 100) -> dict[str, int]:
    """Publish a batch of ready outbox events."""

    from agentproof_backend.apps.outbox.services import publish_pending_outbox_events

    result = publish_pending_outbox_events(batch_size=batch_size)
    return {
        "selected": result.selected,
        "published": result.published,
        "failed": result.failed,
        "retried": result.retried,
    }


@shared_task(name="outbox.recover_stale_events")
def recover_stale_events(stale_minutes: int = 15, batch_size: int = 500) -> int:
    """Recover abandoned outbox events left in publishing state."""

    from agentproof_backend.apps.outbox.services import recover_stale_outbox_events

    return recover_stale_outbox_events(stale_minutes=stale_minutes, batch_size=batch_size)
