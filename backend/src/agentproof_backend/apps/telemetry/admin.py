"""Django admin for canonical telemetry."""

from typing import TYPE_CHECKING

from django.contrib import admin

from agentproof_backend.apps.telemetry.models import Span, SpanEvent, Trace, TraceAnnotation

if TYPE_CHECKING:
    TraceAdminBase = admin.ModelAdmin[Trace]
    SpanAdminBase = admin.ModelAdmin[Span]
    SpanEventAdminBase = admin.ModelAdmin[SpanEvent]
    TraceAnnotationAdminBase = admin.ModelAdmin[TraceAnnotation]
else:
    TraceAdminBase = admin.ModelAdmin
    SpanAdminBase = admin.ModelAdmin
    SpanEventAdminBase = admin.ModelAdmin
    TraceAnnotationAdminBase = admin.ModelAdmin


@admin.register(Trace)
class TraceAdmin(TraceAdminBase):
    """Admin view for canonical traces."""

    list_display = ("name", "external_trace_id", "environment", "project", "status", "started_at")
    list_filter = ("organization", "project", "environment", "status")
    search_fields = ("name", "external_trace_id", "session_identifier", "user_identifier")
    readonly_fields = ("id", "organization", "project", "created_at", "updated_at")


@admin.register(Span)
class SpanAdmin(SpanAdminBase):
    """Admin view for canonical spans."""

    list_display = ("name", "external_span_id", "trace", "span_type", "status", "started_at")
    list_filter = ("organization", "span_type", "status")
    search_fields = ("name", "external_span_id", "parent_external_span_id", "trace__external_trace_id")
    readonly_fields = ("id", "organization", "created_at", "updated_at")


@admin.register(SpanEvent)
class SpanEventAdmin(SpanEventAdminBase):
    """Admin view for span events."""

    list_display = ("name", "span", "organization", "occurred_at")
    list_filter = ("organization", "name")
    search_fields = ("name", "span__external_span_id", "span__trace__external_trace_id")
    readonly_fields = ("id", "organization")


@admin.register(TraceAnnotation)
class TraceAnnotationAdmin(TraceAnnotationAdminBase):
    """Admin view for trace annotations."""

    list_display = ("annotation_type", "trace", "author", "organization", "created_at")
    list_filter = ("organization", "annotation_type")
    search_fields = ("annotation_type", "comment", "trace__external_trace_id")
    readonly_fields = ("id", "organization", "created_at")
