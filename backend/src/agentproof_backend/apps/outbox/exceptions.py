"""Outbox domain exceptions."""


class OutboxError(Exception):
    """Base class for outbox failures."""


class UnknownOutboxEventType(OutboxError):
    """Raised when no publisher is registered for an event type."""
