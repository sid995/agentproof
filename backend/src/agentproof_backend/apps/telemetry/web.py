"""Trace explorer web views."""

from typing import Any
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.selectors import environments_for_project, projects_for_organization
from agentproof_backend.apps.telemetry.exceptions import TraceNotFound
from agentproof_backend.apps.telemetry.forms import TraceAnnotationForm
from agentproof_backend.apps.telemetry.models import TraceStatus
from agentproof_backend.apps.telemetry.selectors import (
    TraceFilters,
    annotations_for_trace,
    get_trace_cost_breakdown,
    get_trace_summary,
    get_trace_token_breakdown,
    get_trace_tree,
    list_traces,
)
from agentproof_backend.apps.telemetry.services import create_trace_annotation


def _current_organization(request: HttpRequest) -> Organization:
    organization = getattr(request, "organization", None)
    if not isinstance(organization, Organization):
        raise PermissionDenied("Select an active organization first.")
    return organization


def _current_user(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied("Authentication is required.")
    return request.user


def _query_value(request: HttpRequest, key: str) -> str:
    value = request.GET.get(key, "")
    return value.strip()


def _cursor_url(*, query_params: dict[str, str], cursor: str) -> str:
    params = dict(query_params)
    if cursor:
        params["cursor"] = cursor
    return f"?{urlencode(params)}" if params else ""


@login_required
def trace_list(request: HttpRequest) -> HttpResponse:
    """Render the tenant-scoped trace list."""

    organization = _current_organization(request)
    selected_project_id = _query_value(request, "project")
    selected_environment_id = _query_value(request, "environment")
    projects = tuple(projects_for_organization(organization=organization))
    selected_project = next((project for project in projects if str(project.id) == selected_project_id), None)
    environments = tuple(
        environments_for_project(organization=organization, project=selected_project) if selected_project else ()
    )

    filters = TraceFilters(
        project_id=selected_project_id or None,
        environment_id=selected_environment_id or None,
        status=_query_value(request, "status"),
        search=_query_value(request, "q"),
        tag=_query_value(request, "tag"),
        cursor=_query_value(request, "cursor"),
    )
    page = list_traces(organization=organization, filters=filters)
    query_params: dict[str, str] = {
        key: value
        for key, value in {
            "project": selected_project_id,
            "environment": selected_environment_id,
            "status": filters.status,
            "q": filters.search,
            "tag": filters.tag,
        }.items()
        if value
    }

    return render(
        request,
        "telemetry/trace_list.html",
        {
            "page": page,
            "projects": projects,
            "environments": environments,
            "statuses": TraceStatus.choices,
            "filters": filters,
            "query_params": query_params,
            "next_url": _cursor_url(query_params=query_params, cursor=page.next_cursor),
            "previous_url": _cursor_url(query_params=query_params, cursor=page.previous_cursor),
        },
    )


@login_required
def trace_detail(request: HttpRequest, trace_id: str) -> HttpResponse:
    """Render one tenant-scoped trace detail page."""

    organization = _current_organization(request)
    try:
        trace = get_trace_summary(organization=organization, trace_id=trace_id)
        tree = get_trace_tree(organization=organization, trace_id=trace.id)
    except TraceNotFound as exc:
        raise Http404("Trace not found.") from exc

    return render(
        request,
        "telemetry/trace_detail.html",
        {
            "trace": trace,
            "tree": tree,
            "cost_breakdown": get_trace_cost_breakdown(organization=organization, trace_id=trace.id),
            "token_breakdown": get_trace_token_breakdown(organization=organization, trace_id=trace.id),
            "annotations": annotations_for_trace(organization=organization, trace=trace),
            "annotation_form": TraceAnnotationForm(),
            "model_spans": [row.span for row in tree.rows if row.span.span_type == "model"],
            "tool_spans": [row.span for row in tree.rows if row.span.span_type == "tool"],
            "error_spans": [row.span for row in tree.rows if row.span.status == "error" or row.span.error_message],
        },
    )


@login_required
@require_http_methods(["POST"])
def trace_annotation_create(request: HttpRequest, trace_id: str) -> HttpResponse:
    """Create a trace annotation from the detail page."""

    organization = _current_organization(request)
    try:
        trace = get_trace_summary(organization=organization, trace_id=trace_id)
    except TraceNotFound as exc:
        raise Http404("Trace not found.") from exc
    form = TraceAnnotationForm(request.POST)
    if form.is_valid():
        create_trace_annotation(
            actor=_current_user(request),
            organization=organization,
            trace=trace,
            annotation_type=form.cleaned_data["annotation_type"],
            comment=form.cleaned_data.get("comment", ""),
        )
        return redirect("trace-web:trace-detail", trace_id=trace.id)

    tree = get_trace_tree(organization=organization, trace_id=trace.id)
    context: dict[str, Any] = {
        "trace": trace,
        "tree": tree,
        "cost_breakdown": get_trace_cost_breakdown(organization=organization, trace_id=trace.id),
        "token_breakdown": get_trace_token_breakdown(organization=organization, trace_id=trace.id),
        "annotations": annotations_for_trace(organization=organization, trace=trace),
        "annotation_form": form,
        "model_spans": [row.span for row in tree.rows if row.span.span_type == "model"],
        "tool_spans": [row.span for row in tree.rows if row.span.span_type == "tool"],
        "error_spans": [row.span for row in tree.rows if row.span.status == "error" or row.span.error_message],
    }
    return render(request, "telemetry/trace_detail.html", context, status=400)
