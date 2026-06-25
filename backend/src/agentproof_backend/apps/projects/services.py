"""State changing project use cases."""

from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.services import record_audit_event
from agentproof_backend.apps.organizations.models import Membership, MembershipRole, MembershipStatus, Organization
from agentproof_backend.apps.projects.exceptions import ProjectConflict, ProjectError, ProjectPermissionDenied
from agentproof_backend.apps.projects.models import CaptureMode, Environment, EnvironmentType, Project
from agentproof_backend.apps.projects.selectors import get_environment_for_organization, get_project_for_organization

MANAGER_ROLES = {MembershipRole.OWNER, MembershipRole.ADMINISTRATOR, MembershipRole.DEVELOPER}


def _require_project_manager(*, actor: User, organization: Organization) -> Membership:
    try:
        membership = Membership.objects.get(organization=organization, user=actor, status=MembershipStatus.ACTIVE)
    except Membership.DoesNotExist as exc:
        raise ProjectPermissionDenied("You are not an active organization member.") from exc

    if membership.role not in MANAGER_ROLES:
        raise ProjectPermissionDenied("Owner or administrator access is required.")

    return membership


def _normalize_slug(*, source: str, requested_slug: str | None) -> str:
    slug_source = requested_slug or source
    slug = slugify(slug_source, allow_unicode=True)[:63].strip("-")

    if not slug:
        raise ProjectError("Slug cannot be empty")

    return slug


def _project_snapshot(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "organization_id": str(project.organization_id),
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "capture_mode": project.capture_mode,
        "retention_days": project.retention_days,
    }


def _environment_snapshot(environment: Environment) -> dict[str, Any]:
    return {
        "id": str(environment.id),
        "organization_id": str(environment.organization_id),
        "project_id": str(environment.project_id),
        "name": environment.name,
        "slug": environment.slug,
        "environment_type": environment.environment_type,
        "capture_mode_override": environment.capture_mode_override,
        "retention_days_override": environment.retention_days_override,
    }


@transaction.atomic
def create_project(
    *,
    actor: User,
    organization: Organization,
    name: str,
    requested_slug: str,
    description: str,
    capture_mode: str,
    retention_days: int,
    audit_context: AuditContext,
) -> Project:
    """Create a tenant scoped project"""

    _require_project_manager(actor=actor, organization=organization)

    if capture_mode not in CaptureMode.values:
        raise ProjectError("Invalid capture mode")

    if retention_days < 1:
        raise ProjectError("Retention days must be positive.")

    project = Project(
        organization=organization,
        name=name.strip(),
        slug=_normalize_slug(source=name, requested_slug=requested_slug),
        description=description.strip(),
        capture_mode=capture_mode,
        retention_days=retention_days,
    )

    if not project.name:
        raise ProjectError("Project name cannot be empty")

    try:
        project.save()
    except IntegrityError as exc:
        raise ProjectConflict("A project with this slug already exist") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        context=audit_context,
        after_state=_project_snapshot(project),
    )

    return project


@transaction.atomic
def update_project(
    *,
    actor: User,
    organization: Organization,
    project_id: UUID | str,
    name: str | None,
    description: str | None,
    capture_mode: str | None,
    retention_days: int | None,
    audit_context: AuditContext,
) -> Project:
    """Update a tenant scoped project"""

    _require_project_manager(actor=actor, organization=organization)

    project = get_project_for_organization(
        organization=organization,
        project_id=project_id,
    )
    before_state = _project_snapshot(project)

    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ProjectError("Project name cannot be empty")
        project.name = normalized_name

    if description is not None:
        project.description = description.strip()

    if capture_mode is not None:
        if capture_mode not in CaptureMode.values:
            raise ProjectError("Invalid capture mode")
        project.capture_mode = capture_mode

    if retention_days is not None:
        if retention_days < 1:
            raise ProjectError("Retention days must be positive")
        project.retention_days = retention_days

    project.save(update_fields=["name", "description", "capture_mode", "retention_days", "updated_at"])

    record_audit_event(
        organization=organization,
        actor=actor,
        action="project.updated",
        resource_type="project",
        resource_id=project.id,
        context=audit_context,
        before_state=before_state,
        after_state=_project_snapshot(project),
    )

    return project


@transaction.atomic
def create_environment(
    *,
    actor: User,
    organization: Organization,
    project_id: UUID | str,
    name: str,
    requested_slug: str | None,
    environment_type: str,
    capture_mode_override: str,
    retention_days_override: int | None,
    audit_context: AuditContext,
) -> Environment:
    """Create an environment under a tenant-scoped project."""

    _require_project_manager(actor=actor, organization=organization)

    project = get_project_for_organization(
        organization=organization,
        project_id=project_id,
    )

    if environment_type not in EnvironmentType.values:
        raise ProjectError("Invalid environment type.")

    if capture_mode_override and capture_mode_override not in CaptureMode.values:
        raise ProjectError("Invalid capture mode override.")

    if retention_days_override is not None and retention_days_override < 1:
        raise ProjectError("Retention override must be positive.")

    environment = Environment(
        organization=organization,
        project=project,
        name=name.strip(),
        slug=_normalize_slug(source=name, requested_slug=requested_slug),
        environment_type=environment_type,
        capture_mode_override=capture_mode_override,
        retention_days_override=retention_days_override,
    )

    if not environment.name:
        raise ProjectError("Environment name cannot be empty.")

    try:
        environment.save()
    except IntegrityError as exc:
        raise ProjectConflict("An environment with this slug already exists in this project.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="environment.created",
        resource_type="environment",
        resource_id=environment.id,
        context=audit_context,
        after_state=_environment_snapshot(environment),
    )

    return environment


@transaction.atomic
def update_environment(
    *,
    actor: User,
    organization: Organization,
    environment_id: UUID | str,
    name: str | None,
    environment_type: str | None,
    capture_mode_override: str | None,
    retention_days_override: int | None,
    clear_retention_days_override: bool,
    audit_context: AuditContext,
) -> Environment:
    """Update a tenant-scoped environment."""

    _require_project_manager(actor=actor, organization=organization)

    environment = get_environment_for_organization(
        organization=organization,
        environment_id=environment_id,
    )
    before_state = _environment_snapshot(environment)

    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ProjectError("Environment name cannot be empty.")
        environment.name = normalized_name

    if environment_type is not None:
        if environment_type not in EnvironmentType.values:
            raise ProjectError("Invalid environment type.")
        environment.environment_type = environment_type

    if capture_mode_override is not None:
        if capture_mode_override and capture_mode_override not in CaptureMode.values:
            raise ProjectError("Invalid capture mode override.")
        environment.capture_mode_override = capture_mode_override

    if clear_retention_days_override:
        environment.retention_days_override = None
    elif retention_days_override is not None:
        if retention_days_override < 1:
            raise ProjectError("Retention override must be positive.")
        environment.retention_days_override = retention_days_override

    environment.save(
        update_fields=(
            "name",
            "environment_type",
            "capture_mode_override",
            "retention_days_override",
            "updated_at",
        )
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="environment.updated",
        resource_type="environment",
        resource_id=environment.id,
        context=audit_context,
        before_state=before_state,
        after_state=_environment_snapshot(environment),
    )

    return environment
