"""Trace tree validation for canonical telemetry"""

from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalTrace
from agentproof_backend.apps.telemetry.exceptions import TelemetryValidationError


def _validate_span_timelines(span: CanonicalSpan) -> None:
    if span.ended_at is not None and span.ended_at < span.started_at:
        raise TelemetryValidationError(f"Span {span.external_span_id} ends before it starts")

    if span.duration_ms is not None and span.duration_ms < 0:
        raise TelemetryValidationError(f"Span {span.external_span_id} has negative duration")


def validate_trace_tree(trace: CanonicalTrace) -> tuple[str, ...]:
    """Validate span identifiers, parent references, timing, and cycles"""

    if not trace.external_trace_id:
        raise TelemetryValidationError("Trace external_trace_id is required")

    if trace.ended_at is not None and trace.ended_at < trace.started_at:
        raise TelemetryValidationError("Trace ends before it starts")

    if trace.duration_ms is not None and trace.duration_ms < 0:
        raise TelemetryValidationError("Trace duration cannot be negative")

    spans_by_id: dict[str, CanonicalSpan] = {}
    for span in trace.spans:
        if not span.external_span_id:
            raise TelemetryValidationError("Span external_span_id is required")

        if span.external_span_id in spans_by_id:
            raise TelemetryValidationError(f"Duplicate span id: {span.external_span_id}")

        _validate_span_timelines(span)
        spans_by_id[span.external_span_id] = span

    if not spans_by_id:
        raise TelemetryValidationError("Trace must contain at least one span")

    for span in spans_by_id.values():
        parent_id = span.parent_external_span_id
        if not parent_id:
            continue

        parent = spans_by_id.get(parent_id)
        if parent is None:
            raise TelemetryValidationError(f"Span {span.external_span_id} references missing parent {parent_id}")

        if parent.ended_at is not None and span.started_at < parent.started_at:
            raise TelemetryValidationError(f"Span {span.external_span_id} starts before parent {parent_id}")

        if parent.ended_at is not None and span.ended_at is not None and span.ended_at > parent.ended_at:
            raise TelemetryValidationError(f"Span {span.external_span_id} ends after parent {parent_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(visit_span_id: str) -> None:
        if visit_span_id in visited:
            return

        if visit_span_id in visiting:
            raise TelemetryValidationError("Trace span tree contains a cycle")

        visiting.add(visit_span_id)
        span_parent_id_external = spans_by_id[visit_span_id].parent_external_span_id
        if span_parent_id_external:
            visit(span_parent_id_external)

        visiting.remove(visit_span_id)
        visited.add(visit_span_id)

    for span_id in spans_by_id:
        visit(span_id)

    root_ids = tuple(span.external_span_id for span in spans_by_id.values() if not span.parent_external_span_id)
    if not root_ids:
        raise TelemetryValidationError("Trace must contain at least one root span")

    return root_ids
