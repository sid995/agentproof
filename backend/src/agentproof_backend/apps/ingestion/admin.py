"""Admin registration for ingestion models."""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from agentproof_backend.apps.ingestion.models import ProcessingStatus, TraceProcessingEvent

if TYPE_CHECKING:
    TraceProcessingEventAdminBase = admin.ModelAdmin[TraceProcessingEvent]
else:
    TraceProcessingEventAdminBase = admin.ModelAdmin


@admin.register(TraceProcessingEvent)
class TraceProcessingEventAdmin(TraceProcessingEventAdminBase):
    list_display = ("id", "trace_id", "organization", "status", "created_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("trace__external_trace_id", "organization__name")
    readonly_fields = ("id", "trace", "organization", "created_at", "updated_at", "processed_at")
    ordering = ("-created_at",)
    actions = ("requeue_pending",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[TraceProcessingEvent]:
        return super().get_queryset(request).select_related("organization", "trace")

    @admin.action(description="Requeue selected events for processing")
    def requeue_pending(self, _request: HttpRequest, queryset: QuerySet[TraceProcessingEvent]) -> None:
        from agentproof_backend.apps.ingestion.tasks import process_trace_events

        for event in queryset.filter(status=ProcessingStatus.PENDING):
            process_trace_events.delay(str(event.id))
