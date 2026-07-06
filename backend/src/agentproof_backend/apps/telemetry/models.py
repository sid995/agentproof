"""Canonical telemetry database models"""

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel, UUIDModel


class TraceStatus(models.TextChoices):
    """Canonical lifecycle outcome for one trace"""

    SUCCESS = "success", "Success"
    ERROR = "error", "Error"
    PARTIAL = "partial", "Partial"
    UNKNOWN = "unknown", "Unknown"


class SpanStatus(models.TextChoices):
    """Canonical lifecycle outcome for one span."""

    SUCCESS = "success", "Success"
    ERROR = "error", "Error"
    UNSET = "unset", "Unset"


class SpanType(models.TextChoices):
    """Canonical operation categories inside a trace tree."""

    AGENT = "agent", "Agent"
    MODEL = "model", "Model"
    TOOL = "tool", "Tool"
    RETRIEVAL = "retrieval", "Retrieval"
    GUARDRAIL = "guardrail", "Guardrail"
    WORKFLOW = "workflow", "Workflow"
    CUSTOM = "custom", "Custom"


class Trace(TimeStampedUUIDModel):
    """Complete model for AI agent execution"""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="traces")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="traces")
    environment = models.ForeignKey("projects.Environment", on_delete=models.CASCADE, related_name="traces")
    external_trace_id = models.CharField(max_length=160)
    schema_version = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=TraceStatus.choices, default=TraceStatus.UNKNOWN, db_index=True)
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField(null=True, blank=True)
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    error_type = models.CharField(max_length=160, blank=True)
    error_message = models.TextField(blank=True)
    total_input_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_output_tokens = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    user_identifier = models.CharField(max_length=200, blank=True)
    session_identifier = models.CharField(max_length=200, blank=True, db_index=True)

    class Meta:
        ordering = ("-started_at", "-created_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organization", "environment", "external_trace_id", "schema_version"),
                name="unique_trace_identity_per_env",
            ),
            models.CheckConstraint(condition=Q(status__in=TraceStatus.values), name="trace_status_valid"),
            models.CheckConstraint(
                condition=Q(duration_ms__isnull=True) | Q(duration_ms__gte=0),
                name="trace_duration_non_negative",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organization", "project", "environment", "-started_at"),
                name="trace_scope_started_idx",
            ),
            models.Index(fields=("organization", "external_trace_id"), name="trace_org_external_idx"),
            models.Index(fields=("organization", "status", "-started_at"), name="trace_org_status_idx"),
            models.Index(fields=("project", "session_identifier"), name="trace_project_session_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.environment} / {self.name}"


class Span(TimeStampedUUIDModel):
    """A timed operation within a trace."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="spans")
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE, related_name="spans")
    external_span_id = models.CharField(max_length=160)
    parent_external_span_id = models.CharField(max_length=160, blank=True)
    span_type = models.CharField(max_length=30, choices=SpanType.choices, default=SpanType.CUSTOM, db_index=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=SpanStatus.choices, default=SpanStatus.UNSET, db_index=True)
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField(null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    error_type = models.CharField(max_length=160, blank=True)
    error_message = models.TextField(blank=True)
    provider_name = models.CharField(max_length=120, blank=True)
    model_name = models.CharField(max_length=160, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ("started_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(fields=("trace", "external_span_id"), name="unique_span_identity_per_trace"),
            models.CheckConstraint(condition=Q(span_type__in=SpanType.values), name="span_type_valid"),
            models.CheckConstraint(condition=Q(status__in=SpanStatus.values), name="span_status_valid"),
            models.CheckConstraint(
                condition=Q(duration_ms__isnull=True) | Q(duration_ms__gte=0),
                name="span_duration_non_negative",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("trace", "parent_external_span_id"), name="span_trace_parent_idx"),
            models.Index(fields=("organization", "span_type", "-started_at"), name="span_org_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.trace.external_trace_id} / {self.name}"


class SpanEvent(UUIDModel):
    """A point-in-time event attached to a span."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="span_events")
    span = models.ForeignKey(Span, on_delete=models.CASCADE, related_name="events")
    name = models.CharField(max_length=200)
    occurred_at = models.DateTimeField(db_index=True)
    attributes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("occurred_at", "id")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("span", "occurred_at"), name="span_event_time_idx"),
            models.Index(fields=("organization", "name"), name="span_event_org_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.span.external_span_id} / {self.name}"


class TraceAnnotation(UUIDModel):
    """Human-authored metadata attached to a trace."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="trace_annotations",
    )
    trace = models.ForeignKey(Trace, on_delete=models.CASCADE, related_name="annotations")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trace_annotations",
    )
    annotation_type = models.CharField(max_length=80)
    value = models.JSONField(default=dict, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "id")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "annotation_type"), name="annotation_org_type_idx"),
            models.Index(fields=("trace", "-created_at"), name="annotation_trace_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.trace.external_trace_id} / {self.annotation_type}"
