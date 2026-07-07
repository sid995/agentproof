"""Ingestion processing event model"""

from typing import ClassVar

from django.db import models
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class TraceProcessingEvent(TimeStampedUUIDModel):
    """Records that a trace was accepted and needs downstream processing"""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="trace_processing_events",
    )
    trace = models.OneToOneField(
        "telemetry.Trace",
        on_delete=models.CASCADE,
        related_name="processing_event",
    )
    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        db_index=True,
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    error_detail = models.TextField(blank=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=ProcessingStatus.values),
                name="trace_processing_event_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organization", "status", "created_at"),
                name="tpe_org_status_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"TraceProcessingEvent({self.trace_id}, {self.status})"
