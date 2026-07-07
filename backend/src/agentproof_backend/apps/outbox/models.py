"""Transactional outbox models."""

from typing import ClassVar

from django.db import models
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel


class OutboxEventStatus(models.TextChoices):
    """Lifecycle states for an outbox event."""

    PENDING = "pending", "Pending"
    PUBLISHING = "publishing", "Publishing"
    PUBLISHED = "published", "Published"
    FAILED = "failed", "Failed"


class OutboxEvent(TimeStampedUUIDModel):
    """Durable record for background work created with a domain transaction."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="outbox_events",
    )
    event_type = models.CharField(max_length=120, db_index=True)
    aggregate_type = models.CharField(max_length=120)
    aggregate_id = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=OutboxEventStatus.choices,
        default=OutboxEventStatus.PENDING,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=OutboxEventStatus.values),
                name="outbox_event_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_count__gte=0),
                name="outbox_attempt_count_non_negative",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("status", "next_attempt_at", "created_at"), name="outbox_ready_idx"),
            models.Index(fields=("status", "locked_at"), name="outbox_locked_idx"),
            models.Index(fields=("organization", "event_type", "created_at"), name="outbox_org_type_created_idx"),
            models.Index(fields=("aggregate_type", "aggregate_id"), name="outbox_aggregate_idx"),
        ]

    def __str__(self) -> str:
        return f"OutboxEvent({self.event_type}, {self.status})"
