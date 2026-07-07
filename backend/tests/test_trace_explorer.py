"""Tests for the Phase 10 trace explorer."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.organizations.constants import ACTIVE_ORGANIZATION_SESSION_KEY
from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project
from agentproof_backend.apps.projects.services import create_project
from agentproof_backend.apps.telemetry.domain import (
    CanonicalSpan,
    CanonicalSpanEvent,
    CanonicalTrace,
    ErrorDetails,
    ModelAttributes,
    TokenUsage,
)
from agentproof_backend.apps.telemetry.exceptions import TraceNotFound
from agentproof_backend.apps.telemetry.models import SpanType, Trace, TraceAnnotation, TraceStatus
from agentproof_backend.apps.telemetry.selectors import (
    TraceFilters,
    get_trace_cost_breakdown,
    get_trace_summary,
    get_trace_token_breakdown,
    get_trace_tree,
    list_traces,
)
from agentproof_backend.apps.telemetry.services import persist_canonical_trace
from tests.organization_helpers import create_test_organization, create_user

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-ten-test",
    source_ip="127.0.0.1",
    user_agent="pytest",
)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def set_active_organization(*, client: APIClient, organization_id: object) -> None:
    session = client.session
    session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization_id)
    session.save()


def create_project_with_default_environment(
    *,
    owner: User,
    organization: Organization,
    name: str = "Support Agent",
    slug: str = "support-agent",
) -> tuple[Project, Environment]:
    result = create_project(
        actor=owner,
        organization=organization,
        name=name,
        requested_slug=slug,
        description="Customer support workflow",
        capture_mode=CaptureMode.FULL,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.project, result.default_environment


def create_trace(
    *,
    organization: Organization,
    project: Project,
    environment: Environment,
    external_trace_id: str = "trace-1",
    name: str = "Failed support run",
    started_offset_minutes: int = 0,
    status: str = TraceStatus.ERROR,
) -> Trace:
    started_at = timezone.now() + timedelta(minutes=started_offset_minutes)
    root_started = started_at
    model_started = started_at + timedelta(milliseconds=100)
    tool_started = started_at + timedelta(milliseconds=450)
    ended_at = started_at + timedelta(milliseconds=1000)

    return persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=CanonicalTrace(
            external_trace_id=external_trace_id,
            schema_version="agentproof.v1",
            name=name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=1000,
            input={"question": "Why did this fail?"},
            output={"answer": "A tool failed."},
            attributes={"workflow": "support"},
            tags=("phase-10", "support"),
            error=ErrorDetails(error_type="ToolError", message="Tool timed out")
            if status == TraceStatus.ERROR
            else None,
            token_usage=TokenUsage(input_tokens=20, output_tokens=30, estimated_cost=Decimal("0.004200")),
            user_identifier="user-123",
            session_identifier="session-456",
            spans=(
                CanonicalSpan(
                    external_span_id="root",
                    name="Support agent",
                    span_type=SpanType.AGENT,
                    status="error" if status == TraceStatus.ERROR else "success",
                    started_at=root_started,
                    ended_at=ended_at,
                    duration_ms=1000,
                    input={"message": "help"},
                    output={"message": "failed"},
                ),
                CanonicalSpan(
                    external_span_id="model",
                    parent_external_span_id="root",
                    name="Classify issue",
                    span_type=SpanType.MODEL,
                    status="success",
                    started_at=model_started,
                    ended_at=started_at + timedelta(milliseconds=400),
                    duration_ms=300,
                    model=ModelAttributes(provider_name="openai", model_name="gpt-test"),
                    token_usage=TokenUsage(input_tokens=12, output_tokens=8, estimated_cost=Decimal("0.001200")),
                    events=(
                        CanonicalSpanEvent(
                            name="model.completed",
                            occurred_at=started_at + timedelta(milliseconds=390),
                            attributes={"finish_reason": "stop"},
                        ),
                    ),
                ),
                CanonicalSpan(
                    external_span_id="tool",
                    parent_external_span_id="root",
                    name="Search documents",
                    span_type=SpanType.TOOL,
                    status="error" if status == TraceStatus.ERROR else "success",
                    started_at=tool_started,
                    ended_at=started_at + timedelta(milliseconds=700),
                    duration_ms=250,
                    input={"query": "refund"},
                    output={"error": "timeout"},
                    error=ErrorDetails(error_type="TimeoutError", message="Search timed out")
                    if status == TraceStatus.ERROR
                    else None,
                    token_usage=TokenUsage(input_tokens=3, output_tokens=0, estimated_cost=Decimal("0.000500")),
                ),
            ),
        ),
    )


def test_list_traces_is_tenant_scoped_and_filterable() -> None:
    owner = create_user(email="owner@example.com")
    other_owner = create_user(email="other-owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    other_organization, _other_membership = create_test_organization(owner=other_owner, name="Other Org")
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    other_project, other_environment = create_project_with_default_environment(
        owner=other_owner,
        organization=other_organization,
        name="Other Project",
        slug="other-project",
    )
    trace = create_trace(organization=organization, project=project, environment=environment)
    create_trace(
        organization=other_organization,
        project=other_project,
        environment=other_environment,
        external_trace_id="other-trace",
    )

    page = list_traces(
        organization=organization,
        filters=TraceFilters(project_id=project.id, environment_id=environment.id, status=TraceStatus.ERROR),
    )

    assert [item.trace.id for item in page.traces] == [trace.id]
    assert page.traces[0].model_names == ("gpt-test",)


def test_trace_cursor_pagination_is_stable() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    older = create_trace(
        organization=organization,
        project=project,
        environment=environment,
        external_trace_id="older",
        name="Older",
        started_offset_minutes=-10,
    )
    newer = create_trace(
        organization=organization,
        project=project,
        environment=environment,
        external_trace_id="newer",
        name="Newer",
        started_offset_minutes=10,
    )

    first_page = list_traces(organization=organization, filters=TraceFilters(limit=1))
    second_page = list_traces(organization=organization, filters=TraceFilters(limit=1, cursor=first_page.next_cursor))

    assert [item.trace.id for item in first_page.traces] == [newer.id]
    assert [item.trace.id for item in second_page.traces] == [older.id]
    assert second_page.previous_cursor


def test_trace_detail_selectors_build_tree_and_breakdowns() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)

    summary = get_trace_summary(organization=organization, trace_id=trace.id)
    tree = get_trace_tree(organization=organization, trace_id=trace.id)
    cost_breakdown = get_trace_cost_breakdown(organization=organization, trace_id=trace.id)
    token_breakdown = get_trace_token_breakdown(organization=organization, trace_id=trace.id)

    assert summary.id == trace.id
    assert [(row.span.external_span_id, row.depth) for row in tree.rows] == [("root", 0), ("model", 1), ("tool", 1)]
    assert tree.rows[1].events[0].name == "model.completed"
    assert {row.span_type: row.estimated_cost for row in cost_breakdown}[SpanType.MODEL] == Decimal("0.001200")
    assert {row.span_type: row.input_tokens for row in token_breakdown}[SpanType.MODEL] == 12


def test_cross_tenant_trace_summary_is_not_visible() -> None:
    owner = create_user(email="owner@example.com")
    other_owner = create_user(email="other-owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    other_organization, _other_membership = create_test_organization(owner=other_owner, name="Other Org")
    other_project, other_environment = create_project_with_default_environment(
        owner=other_owner,
        organization=other_organization,
        name="Other Project",
        slug="other-project",
    )
    other_trace = create_trace(
        organization=other_organization,
        project=other_project,
        environment=other_environment,
        external_trace_id="other-trace",
    )

    with pytest.raises(TraceNotFound):
        get_trace_summary(organization=organization, trace_id=other_trace.id)


def test_trace_list_selector_query_count_is_bounded() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    create_trace(organization=organization, project=project, environment=environment)

    with CaptureQueriesContext(connection) as queries:
        page = list_traces(organization=organization, filters=TraceFilters())

    assert len(page.traces) == 1
    assert len(queries) <= 2


def test_trace_tree_selector_query_count_is_bounded() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)

    with CaptureQueriesContext(connection) as queries:
        tree = get_trace_tree(organization=organization, trace_id=trace.id)

    assert len(tree.rows) == 3
    assert len(queries) <= 3


def test_trace_list_requires_login() -> None:
    client = APIClient()

    response = client.get("/traces/")

    assert response.status_code == 302
    assert "/api-auth/login/" in response["Location"]


def test_trace_list_page_renders_failed_trace() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get("/traces/", {"status": TraceStatus.ERROR})

    assert response.status_code == 200
    assert trace.name.encode() in response.content
    assert b"gpt-test" in response.content


def test_trace_detail_page_renders_diagnostics() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/traces/{trace.id}/")

    assert response.status_code == 200
    assert b"Span Waterfall" in response.content
    assert b"Search documents" in response.content
    assert b"Tool timed out" in response.content


def test_cross_tenant_trace_detail_returns_404() -> None:
    owner = create_user(email="owner@example.com")
    other_owner = create_user(email="other-owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    other_organization, _other_membership = create_test_organization(owner=other_owner, name="Other Org")
    other_project, other_environment = create_project_with_default_environment(
        owner=other_owner,
        organization=other_organization,
        name="Other Project",
        slug="other-project",
    )
    other_trace = create_trace(
        organization=other_organization,
        project=other_project,
        environment=other_environment,
        external_trace_id="other-trace",
    )
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/traces/{other_trace.id}/")

    assert response.status_code == 404


def test_trace_annotation_create_records_author() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.post(
        f"/traces/{trace.id}/annotations/",
        {"annotation_type": "diagnosis", "comment": "Retry the tool call."},
    )

    assert response.status_code == 302
    annotation = TraceAnnotation.objects.get(trace=trace)
    assert annotation.organization == organization
    assert annotation.author == owner
    assert annotation.comment == "Retry the tool call."


def test_trace_list_filter_search_matches_error_text() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_default_environment(owner=owner, organization=organization)
    trace = create_trace(organization=organization, project=project, environment=environment)
    create_trace(
        organization=organization,
        project=project,
        environment=environment,
        external_trace_id="successful",
        name="Successful support run",
        started_offset_minutes=5,
        status=TraceStatus.SUCCESS,
    )

    page = list_traces(organization=organization, filters=TraceFilters(search="timed out"))

    assert [item.trace.id for item in page.traces] == [trace.id]
