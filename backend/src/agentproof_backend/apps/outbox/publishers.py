"""Event publisher registry for the transactional outbox."""

from collections.abc import Callable

from agentproof_backend.apps.outbox.exceptions import UnknownOutboxEventType
from agentproof_backend.apps.outbox.models import OutboxEvent

TRACE_ACCEPTED = "trace.accepted"

Publisher = Callable[[OutboxEvent], None]


def publish_trace_accepted(event: OutboxEvent) -> None:
    """Publish trace post-processing work to Celery."""

    from agentproof_backend.apps.ingestion.tasks import process_trace_events

    processing_event_id = str(event.payload["processing_event_id"])
    process_trace_events.delay(processing_event_id)


PUBLISHERS: dict[str, Publisher] = {
    TRACE_ACCEPTED: publish_trace_accepted,
}


def publish_outbox_event(event: OutboxEvent) -> None:
    """Publish a single outbox event through its registered dispatcher."""

    try:
        publisher = PUBLISHERS[event.event_type]
    except KeyError as exc:
        raise UnknownOutboxEventType(f"No publisher registered for {event.event_type}") from exc

    publisher(event)
