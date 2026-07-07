"""Admin registration for transactional outbox events."""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone

from agentproof_backend.apps.outbox.models import OutboxEvent, OutboxEventStatus

if TYPE_CHECKING:
    OutboxEventAdminBase = admin.ModelAdmin[OutboxEvent]
else:
    OutboxEventAdminBase = admin.ModelAdmin


@admin.register(OutboxEvent)
class OutboxEventAdmin(OutboxEventAdminBase):
    """Read-mostly admin surface for outbox operations."""

    list_display = ("id", "event_type", "aggregate_type", "status", "attempt_count", "created_at", "published_at")
    list_filter = ("status", "event_type", "aggregate_type")
    search_fields = ("event_type", "aggregate_type", "aggregate_id", "organization__name")
    readonly_fields = (
        "id",
        "organization",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "payload",
        "created_at",
        "updated_at",
        "published_at",
        "last_error",
    )
    ordering = ("-created_at",)
    actions = ("requeue_selected",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[OutboxEvent]:
        return super().get_queryset(request).select_related("organization")

    @admin.action(description="Requeue selected pending or failed events")
    def requeue_selected(self, _request: HttpRequest, queryset: QuerySet[OutboxEvent]) -> None:
        queryset.filter(status__in=[OutboxEventStatus.PENDING, OutboxEventStatus.FAILED]).update(
            status=OutboxEventStatus.PENDING,
            locked_at=None,
            next_attempt_at=timezone.now(),
            last_error="",
        )
