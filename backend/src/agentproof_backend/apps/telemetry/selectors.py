"""Read-focused trace explorer queries."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from django.db.models import Prefetch, Q, QuerySet, Sum
from django.utils.dateparse import parse_datetime

from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.telemetry.exceptions import TraceNotFound
from agentproof_backend.apps.telemetry.models import Span, SpanEvent, Trace, TraceAnnotation

CursorDirection = Literal["after", "before"]


@dataclass(frozen=True)
class TraceFilters:
    """Trace list filters from web query parameters."""

    project_id: UUID | str | None = None
    environment_id: UUID | str | None = None
    status: str = ""
    search: str = ""
    tag: str = ""
    cursor: str = ""
    limit: int = 25


@dataclass(frozen=True)
class TraceListItem:
    """A trace plus display metadata for the list page."""

    trace: Trace
    model_names: tuple[str, ...]


@dataclass(frozen=True)
class TraceListPage:
    """Cursor-paginated trace list result."""

    traces: tuple[TraceListItem, ...]
    next_cursor: str
    previous_cursor: str


@dataclass(frozen=True)
class SpanTreeRow:
    """A span row ready for tree and waterfall rendering."""

    span: Span
    depth: int
    offset_percent: Decimal
    width_percent: Decimal
    events: tuple[SpanEvent, ...]


@dataclass(frozen=True)
class TraceTree:
    """Hierarchical trace details and waterfall rows."""

    trace: Trace
    rows: tuple[SpanTreeRow, ...]


@dataclass(frozen=True)
class BreakdownRow:
    """Aggregated cost or token usage by span type."""

    span_type: str
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal


def _encode_cursor(*, direction: CursorDirection, trace: Trace) -> str:
    payload = {
        "direction": direction,
        "started_at": trace.started_at.isoformat(),
        "id": str(trace.id),
    }
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[CursorDirection, datetime, str] | None:
    if not cursor:
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, json.JSONDecodeError):
        return None

    direction = payload.get("direction")
    started_at_raw = payload.get("started_at")
    trace_id = payload.get("id")
    if direction not in {"after", "before"} or not isinstance(started_at_raw, str) or not isinstance(trace_id, str):
        return None

    started_at = parse_datetime(started_at_raw)
    if started_at is None:
        return None

    return direction, started_at, trace_id


def _base_trace_queryset(*, organization: Organization) -> QuerySet[Trace]:
    model_spans = Span.objects.filter(span_type="model").order_by("started_at", "id")
    return (
        Trace.objects.filter(organization=organization)
        .select_related("organization", "project", "environment")
        .prefetch_related(Prefetch("spans", queryset=model_spans, to_attr="model_spans"))
    )


def _apply_trace_filters(*, queryset: QuerySet[Trace], filters: TraceFilters) -> QuerySet[Trace]:
    if filters.project_id:
        queryset = queryset.filter(project_id=filters.project_id)
    if filters.environment_id:
        queryset = queryset.filter(environment_id=filters.environment_id)
    if filters.status:
        queryset = queryset.filter(status=filters.status)
    if filters.search:
        queryset = queryset.filter(
            Q(name__icontains=filters.search)
            | Q(external_trace_id__icontains=filters.search)
            | Q(session_identifier__icontains=filters.search)
            | Q(user_identifier__icontains=filters.search)
            | Q(error_type__icontains=filters.search)
            | Q(error_message__icontains=filters.search)
        )
    if filters.tag:
        queryset = queryset.filter(tags__icontains=filters.tag)

    return queryset


def _apply_cursor(*, queryset: QuerySet[Trace], cursor: str) -> tuple[QuerySet[Trace], CursorDirection | None]:
    decoded = _decode_cursor(cursor)
    if decoded is None:
        return queryset.order_by("-started_at", "-id"), None

    direction, started_at, trace_id = decoded
    if direction == "after":
        queryset = queryset.filter(Q(started_at__lt=started_at) | Q(started_at=started_at, id__lt=trace_id)).order_by(
            "-started_at",
            "-id",
        )
    else:
        queryset = queryset.filter(Q(started_at__gt=started_at) | Q(started_at=started_at, id__gt=trace_id)).order_by(
            "started_at",
            "id",
        )

    return queryset, direction


def _model_names(trace: Trace) -> tuple[str, ...]:
    spans = getattr(trace, "model_spans", [])
    names = {span.model_name for span in spans if isinstance(span, Span) and span.model_name}
    return tuple(sorted(names))


def list_traces(
    *,
    organization: Organization,
    filters: TraceFilters,
) -> TraceListPage:
    """Return tenant-scoped traces with stable cursor pagination."""

    limit = max(1, min(filters.limit, 100))
    queryset = _apply_trace_filters(queryset=_base_trace_queryset(organization=organization), filters=filters)
    queryset, direction = _apply_cursor(queryset=queryset, cursor=filters.cursor)

    raw_traces = list(queryset[: limit + 1])
    has_more = len(raw_traces) > limit
    page_traces = raw_traces[:limit]
    if direction == "before":
        page_traces = list(reversed(page_traces))

    items = tuple(TraceListItem(trace=trace, model_names=_model_names(trace)) for trace in page_traces)
    next_cursor = ""
    previous_cursor = ""
    if items:
        if has_more or direction == "before":
            next_cursor = _encode_cursor(direction="after", trace=items[-1].trace)
        if direction == "after" or direction == "before":
            previous_cursor = _encode_cursor(direction="before", trace=items[0].trace)

    return TraceListPage(traces=items, next_cursor=next_cursor, previous_cursor=previous_cursor)


def get_trace_summary(
    *,
    organization: Organization,
    trace_id: UUID | str,
) -> Trace:
    """Return one tenant-scoped trace summary."""

    try:
        return (
            Trace.objects.filter(organization=organization)
            .select_related("organization", "project", "environment")
            .prefetch_related("annotations__author")
            .get(id=trace_id)
        )
    except Trace.DoesNotExist as exc:
        raise TraceNotFound("The trace does not exist.") from exc


def _span_percentages(*, trace: Trace, span: Span) -> tuple[Decimal, Decimal]:
    trace_duration = trace.duration_ms or 0
    if trace_duration <= 0:
        return Decimal("0"), Decimal("0")

    offset_ms = max(0, int((span.started_at - trace.started_at).total_seconds() * 1000))
    width_ms = span.duration_ms or 0
    offset = min(Decimal("100"), (Decimal(offset_ms) / Decimal(trace_duration)) * Decimal("100"))
    width = min(Decimal("100"), (Decimal(width_ms) / Decimal(trace_duration)) * Decimal("100"))
    return offset.quantize(Decimal("0.01")), width.quantize(Decimal("0.01"))


def get_trace_tree(
    *,
    organization: Organization,
    trace_id: UUID | str,
) -> TraceTree:
    """Return a tenant-scoped trace with ordered tree and waterfall rows."""

    event_queryset = SpanEvent.objects.order_by("occurred_at", "id")
    try:
        trace = (
            Trace.objects.filter(organization=organization)
            .select_related("organization", "project", "environment")
            .prefetch_related(Prefetch("spans__events", queryset=event_queryset))
            .get(id=trace_id)
        )
    except Trace.DoesNotExist as exc:
        raise TraceNotFound("The trace does not exist.") from exc

    spans = sorted(trace.spans.all(), key=lambda span: (span.started_at, span.id))
    spans_by_external_id = {span.external_span_id: span for span in spans}
    children_by_parent: dict[str, list[Span]] = {}
    roots: list[Span] = []
    for span in spans:
        if span.parent_external_span_id and span.parent_external_span_id in spans_by_external_id:
            children_by_parent.setdefault(span.parent_external_span_id, []).append(span)
        else:
            roots.append(span)

    rows: list[SpanTreeRow] = []

    def append_span(span: Span, depth: int) -> None:
        offset, width = _span_percentages(trace=trace, span=span)
        rows.append(
            SpanTreeRow(
                span=span,
                depth=depth,
                offset_percent=offset,
                width_percent=width,
                events=tuple(span.events.all()),
            )
        )
        for child in children_by_parent.get(span.external_span_id, []):
            append_span(child, depth + 1)

    for root in roots:
        append_span(root, 0)

    return TraceTree(trace=trace, rows=tuple(rows))


def get_trace_cost_breakdown(
    *,
    organization: Organization,
    trace_id: UUID | str,
) -> tuple[BreakdownRow, ...]:
    """Return span estimated cost grouped by span type."""

    rows = (
        Span.objects.filter(organization=organization, trace_id=trace_id)
        .values("span_type")
        .annotate(estimated_cost=Sum("estimated_cost"))
        .order_by("span_type")
    )
    return tuple(
        BreakdownRow(
            span_type=str(row["span_type"]),
            input_tokens=0,
            output_tokens=0,
            estimated_cost=row["estimated_cost"] or Decimal("0"),
        )
        for row in rows
    )


def get_trace_token_breakdown(
    *,
    organization: Organization,
    trace_id: UUID | str,
) -> tuple[BreakdownRow, ...]:
    """Return span token usage grouped by span type."""

    rows = (
        Span.objects.filter(organization=organization, trace_id=trace_id)
        .values("span_type")
        .annotate(input_tokens=Sum("input_tokens"), output_tokens=Sum("output_tokens"))
        .order_by("span_type")
    )
    return tuple(
        BreakdownRow(
            span_type=str(row["span_type"]),
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            estimated_cost=Decimal("0"),
        )
        for row in rows
    )


def annotations_for_trace(
    *,
    organization: Organization,
    trace: Trace,
) -> QuerySet[TraceAnnotation]:
    """Return annotations for a tenant-scoped trace."""

    return TraceAnnotation.objects.filter(organization=organization, trace=trace).select_related("author")
