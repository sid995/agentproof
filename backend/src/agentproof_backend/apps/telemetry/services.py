"""State changing telemetry services"""

from django.db import IntegrityError, transaction

from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.models import Environment, Project
from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalTrace
from agentproof_backend.apps.telemetry.exceptions import TelemetryPersistenceError
from agentproof_backend.apps.telemetry.models import Span, SpanEvent, Trace
from agentproof_backend.apps.telemetry.validation import validate_trace_tree


def _require_scope_consistency(*, organization: Organization, project: Project, environment: Environment) -> None:
    if project.organization_id != organization.id:
        raise TelemetryPersistenceError("Project does not belong to the organization")

    if environment.organization_id != organization.id or environment.project_id != project.id:
        raise TelemetryPersistenceError("Environment does not belong to the project and organization")


def _span_error_type(span: CanonicalSpan) -> str:
    return span.error.error_type if span.error else ""


def _span_error_message(span: CanonicalSpan) -> str:
    return span.error.message if span.error else ""


@transaction.atomic
def persist_canonical_trace(
    *,
    organization: Organization,
    project: Project,
    environment: Environment,
    canonical_trace: CanonicalTrace,
) -> Trace:
    """Validate and persist one canonical trace with spans and events"""

    _require_scope_consistency(organization=organization, project=project, environment=environment)
    validate_trace_tree(canonical_trace)

    try:
        trace = Trace.objects.create(
            organization=organization,
            project=project,
            environment=environment,
            external_trace_id=canonical_trace.external_trace_id,
            schema_version=canonical_trace.schema_version,
            name=canonical_trace.name,
            status=canonical_trace.status,
            started_at=canonical_trace.started_at,
            ended_at=canonical_trace.ended_at,
            duration_ms=canonical_trace.duration_ms,
            input=dict(canonical_trace.input),
            output=dict(canonical_trace.output),
            attributes=dict(canonical_trace.attributes),
            tags=list(canonical_trace.tags),
            error_type=canonical_trace.error.error_type if canonical_trace.error else "",
            error_message=canonical_trace.error.message if canonical_trace.error else "",
            total_input_tokens=canonical_trace.token_usage.input_tokens if canonical_trace.token_usage else None,
            total_output_tokens=canonical_trace.token_usage.output_tokens if canonical_trace.token_usage else None,
            estimated_cost=canonical_trace.token_usage.estimated_cost if canonical_trace.token_usage else None,
            user_identifier=canonical_trace.user_identifier,
            session_identifier=canonical_trace.session_identifier,
        )
    except IntegrityError as exc:
        raise TelemetryPersistenceError("Trace could not be persisted") from exc

    spans_by_external_id: dict[str, Span] = {}
    for canonical_span in canonical_trace.spans:
        span = Span.objects.create(
            organization=organization,
            trace=trace,
            external_span_id=canonical_span.external_span_id,
            parent_external_span_id=canonical_span.parent_external_span_id,
            span_type=canonical_span.span_type,
            name=canonical_span.name,
            status=canonical_span.status,
            started_at=canonical_span.started_at,
            ended_at=canonical_span.ended_at,
            duration_ms=canonical_span.duration_ms,
            attributes=dict(canonical_span.attributes),
            input=dict(canonical_span.input),
            output=dict(canonical_span.output),
            error_type=_span_error_type(canonical_span),
            error_message=_span_error_message(canonical_span),
            provider_name=canonical_span.model.provider_name if canonical_span.model else "",
            model_name=canonical_span.model.model_name if canonical_span.model else "",
            input_tokens=canonical_span.token_usage.input_tokens if canonical_span.token_usage else None,
            output_tokens=canonical_span.token_usage.output_tokens if canonical_span.token_usage else None,
            estimated_cost=canonical_span.token_usage.estimated_cost if canonical_span.token_usage else None,
        )
        spans_by_external_id[canonical_span.external_span_id] = span

    span_events = [
        SpanEvent(
            organization=organization,
            span=spans_by_external_id[canonical_span.external_span_id],
            name=event.name,
            occurred_at=event.occurred_at,
            attributes=dict(event.attributes),
        )
        for canonical_span in canonical_trace.spans
        for event in canonical_span.events
    ]

    SpanEvent.objects.bulk_create(span_events)

    return trace
