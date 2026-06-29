"""Minimal project web views."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import audit_context_from_request
from agentproof_backend.apps.organizations.models import Membership, MembershipRole, Organization
from agentproof_backend.apps.projects.forms import EnvironmentForm, ProjectForm
from agentproof_backend.apps.projects.selectors import (
    environments_for_project,
    get_environment_for_organization,
    get_project_for_organization,
    projects_for_organization,
)
from agentproof_backend.apps.projects.services import (
    create_environment,
    create_project,
)


def _current_organization(request: HttpRequest) -> Organization:
    organization = getattr(request, "organization", None)
    if not isinstance(organization, Organization):
        raise PermissionDenied("Select an active organization first.")
    return organization


def _current_user(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied("Authentication is required.")
    return request.user


def _can_manage_projects(request: HttpRequest) -> bool:
    membership = getattr(request, "organization_membership", None)
    if not isinstance(membership, Membership):
        return False

    return isinstance(membership, Membership) and membership.role in {
        MembershipRole.OWNER,
        MembershipRole.ADMINISTRATOR,
        MembershipRole.DEVELOPER,
    }


@login_required
@require_http_methods(["GET", "POST"])
def project_list(request: HttpRequest) -> HttpResponse:
    organization = _current_organization(request)
    form = ProjectForm(request.POST or None)

    if request.method == "POST":
        if not _can_manage_projects(request):
            raise PermissionDenied("Owner, administrator, or developer access is required.")

        if form.is_valid():
            create_project(
                actor=_current_user(request),
                organization=organization,
                name=form.cleaned_data["name"],
                requested_slug=form.cleaned_data.get("slug"),
                description=form.cleaned_data.get("description", ""),
                capture_mode=form.cleaned_data["capture_mode"],
                retention_days=form.cleaned_data["retention_days"],
                audit_context=audit_context_from_request(request),
            )
            return redirect("project-web:project-list")

    return render(
        request,
        "projects/project_list.html",
        {
            "form": form,
            "projects": projects_for_organization(organization=organization),
            "can_manage": _can_manage_projects(request),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_detail(request: HttpRequest, project_id: str) -> HttpResponse:
    organization = _current_organization(request)
    project = get_project_for_organization(organization=organization, project_id=project_id)
    form = EnvironmentForm(request.POST or None)

    if request.method == "POST":
        if not _can_manage_projects(request):
            raise PermissionDenied("Owner, administrator, or developer access is required.")

        if form.is_valid():
            create_environment(
                actor=_current_user(request),
                organization=organization,
                project_id=project.id,
                name=form.cleaned_data["name"],
                requested_slug=form.cleaned_data.get("slug"),
                environment_type=form.cleaned_data["environment_type"],
                capture_mode_override=form.cleaned_data.get("capture_mode_override", ""),
                retention_days_override=form.cleaned_data.get("retention_days_override"),
                audit_context=audit_context_from_request(request),
            )
            return redirect("project-web:project-detail", project_id=project.id)

    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "form": form,
            "environments": environments_for_project(organization=_current_organization(request), project=project),
            "can_manage": _can_manage_projects(request),
        },
    )


@login_required
def environment_detail(request: HttpRequest, environment_id: str) -> HttpResponse:
    organization = _current_organization(request)
    environment = get_environment_for_organization(
        organization=organization,
        environment_id=environment_id,
    )

    return render(
        request,
        "projects/environment_detail.html",
        {
            "environment": environment,
            "effective_capture_mode": environment.capture_mode_override or environment.project.capture_mode,
            "effective_retention_days": environment.retention_days_override or environment.project.retention_days,
        },
    )
