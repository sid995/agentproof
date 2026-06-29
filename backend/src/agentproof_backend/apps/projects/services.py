"""State-changing project and environment use cases."""

import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.services import record_audit_event
from agentproof_backend.apps.organizations.models import (
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from agentproof_backend.apps.projects.exceptions import (
    EnvironmentConflict,
    EnvironmentNotFound,
    InvalidEnvironmentConfiguration,
    InvalidProjectConfiguration,
    ProjectConflict,
    ProjectInactive,
    ProjectNotFound,
    ProjectPermissionDenied,
)
from agentproof_backend.apps.projects.models import (
    MAX_RETENTION_DAYS,
    MIN_RETENTION_DAYS,
    CaptureMode,
    Environment,
    EnvironmentType,
    Project,
    ResourceStatus,
)

PROJECT_ADMIN_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMINISTRATOR,
}

PROJECT_RESOURCE_MANAGER_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMINISTRATOR,
    MembershipRole.DEVELOPER,
}


@dataclass(frozen=True, slots=True)
class CreatedProject:
    """New project and its automatically created environment."""

    project: Project
    default_environment: Environment


def project_snapshot(
    project: Project,
) -> dict[str, Any]:
    """Create a serializable project audit snapshot."""
    return {
        "id": str(project.id),
        "organization_id": str(project.organization_id),
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "status": project.status,
        "capture_mode": project.capture_mode,
        "retention_days": project.retention_days,
    }


def environment_snapshot(
    environment: Environment,
) -> dict[str, Any]:
    """Create a serializable environment audit snapshot."""
    return {
        "id": str(environment.id),
        "organization_id": str(environment.organization_id),
        "project_id": str(environment.project_id),
        "name": environment.name,
        "slug": environment.slug,
        "environment_type": environment.environment_type,
        "status": environment.status,
        "capture_mode_override": environment.capture_mode_override,
        "retention_days_override": (environment.retention_days_override),
        "effective_capture_mode": (environment.effective_capture_mode),
        "effective_retention_days": (environment.effective_retention_days),
    }


def _get_actor_membership(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    if organization.status != OrganizationStatus.ACTIVE:
        raise ProjectPermissionDenied("The organization is not active.")

    try:
        return Membership.objects.get(
            organization=organization,
            user=actor,
            status=MembershipStatus.ACTIVE,
        )
    except Membership.DoesNotExist as exc:
        raise ProjectPermissionDenied("You are not an active organization member.") from exc


def _require_project_administrator(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    membership = _get_actor_membership(
        actor=actor,
        organization=organization,
    )

    if membership.role not in PROJECT_ADMIN_ROLES:
        raise ProjectPermissionDenied("Owner or administrator access is required.")

    return membership


def _require_project_resource_manager(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    membership = _get_actor_membership(
        actor=actor,
        organization=organization,
    )

    if membership.role not in PROJECT_RESOURCE_MANAGER_ROLES:
        raise ProjectPermissionDenied("Owner, administrator, or developer access is required.")

    return membership


def _validate_capture_mode(capture_mode: str) -> None:
    if capture_mode not in CaptureMode.values:
        raise InvalidProjectConfiguration("Invalid capture mode.")


def _validate_retention_days(retention_days: int) -> None:
    if not (MIN_RETENTION_DAYS <= retention_days <= MAX_RETENTION_DAYS):
        raise InvalidProjectConfiguration(
            f"Retention must be between {MIN_RETENTION_DAYS} and {MAX_RETENTION_DAYS} days."
        )


def _validate_environment_retention_days(
    retention_days: int | None,
) -> None:
    if retention_days is None:
        return

    if not (MIN_RETENTION_DAYS <= retention_days <= MAX_RETENTION_DAYS):
        raise InvalidEnvironmentConfiguration(
            f"Environment retention must be between {MIN_RETENTION_DAYS} and {MAX_RETENTION_DAYS} days."
        )


def _validate_environment_capture_mode(
    capture_mode: str | None,
) -> None:
    if capture_mode is None:
        return

    if capture_mode not in CaptureMode.values:
        raise InvalidEnvironmentConfiguration("Invalid environment capture mode.")


def _build_available_project_slug(
    *,
    organization: Organization,
    name: str,
    requested_slug: str | None,
) -> str:
    source = requested_slug or name

    base_slug = slugify(
        source,
        allow_unicode=True,
    )[:63].strip("-")

    if not base_slug:
        base_slug = f"project-{uuid.uuid4().hex[:8]}"

    candidate = base_slug

    while Project.objects.filter(
        organization=organization,
        slug=candidate,
    ).exists():
        suffix = uuid.uuid4().hex[:8]
        candidate = f"{base_slug[:54]}-{suffix}"

    return candidate


def _build_available_environment_slug(
    *,
    project: Project,
    name: str,
    requested_slug: str | None,
) -> str:
    source = requested_slug or name

    base_slug = slugify(
        source,
        allow_unicode=True,
    )[:63].strip("-")

    if not base_slug:
        base_slug = f"environment-{uuid.uuid4().hex[:8]}"

    candidate = base_slug

    while Environment.objects.filter(
        project=project,
        slug=candidate,
    ).exists():
        suffix = uuid.uuid4().hex[:8]
        candidate = f"{base_slug[:54]}-{suffix}"

    return candidate


def _get_locked_project(
    *,
    organization: Organization,
    project_id: UUID | str,
) -> Project:
    try:
        return (
            Project.objects.select_for_update()
            .select_related(
                "organization",
                "created_by",
            )
            .get(
                id=project_id,
                organization=organization,
            )
        )
    except Project.DoesNotExist as exc:
        raise ProjectNotFound("The project does not exist.") from exc


def _get_locked_environment(
    *,
    organization: Organization,
    project: Project,
    environment_id: UUID | str,
) -> Environment:
    try:
        return (
            Environment.objects.select_for_update()
            .select_related(
                "organization",
                "project",
                "created_by",
            )
            .get(
                id=environment_id,
                organization=organization,
                project=project,
            )
        )
    except Environment.DoesNotExist as exc:
        raise EnvironmentNotFound("The environment does not exist.") from exc


@transaction.atomic
def create_project(
    *,
    actor: User,
    organization: Organization,
    name: str,
    requested_slug: str | None,
    description: str,
    capture_mode: str,
    retention_days: int,
    audit_context: AuditContext,
) -> CreatedProject:
    """Create a project with a default development environment."""
    _require_project_administrator(
        actor=actor,
        organization=organization,
    )

    normalized_name = name.strip()

    if not normalized_name:
        raise InvalidProjectConfiguration("Project name cannot be empty.")

    _validate_capture_mode(capture_mode)
    _validate_retention_days(retention_days)

    slug = _build_available_project_slug(
        organization=organization,
        name=normalized_name,
        requested_slug=requested_slug,
    )

    try:
        project = Project.objects.create(
            organization=organization,
            name=normalized_name,
            slug=slug,
            description=description.strip(),
            status=ResourceStatus.ACTIVE,
            capture_mode=capture_mode,
            retention_days=retention_days,
            created_by=actor,
        )

        environment = Environment.objects.create(
            organization=organization,
            project=project,
            name="Development",
            slug="development",
            environment_type=EnvironmentType.DEVELOPMENT,
            status=ResourceStatus.ACTIVE,
            capture_mode_override="",
            retention_days_override=None,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise ProjectConflict("The project or default environment conflicts with an existing resource.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="project.created",
        resource_type="project",
        resource_id=project.id,
        context=audit_context,
        after_state=project_snapshot(project),
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="environment.created",
        resource_type="environment",
        resource_id=environment.id,
        context=audit_context,
        after_state=environment_snapshot(environment),
        metadata={
            "created_automatically": True,
        },
    )

    return CreatedProject(
        project=project,
        default_environment=environment,
    )


@transaction.atomic
def update_project(
    *,
    actor: User,
    organization: Organization,
    project_id: UUID | str,
    name: str | None,
    description: str | None,
    status: str | None,
    capture_mode: str | None,
    retention_days: int | None,
    audit_context: AuditContext,
) -> Project:
    """Update mutable project configuration."""
    _require_project_administrator(
        actor=actor,
        organization=organization,
    )

    project = _get_locked_project(
        organization=organization,
        project_id=project_id,
    )

    before_state = project_snapshot(project)

    if name is not None:
        normalized_name = name.strip()

        if not normalized_name:
            raise InvalidProjectConfiguration("Project name cannot be empty.")

        project.name = normalized_name

    if description is not None:
        project.description = description.strip()

    if status is not None:
        if status not in ResourceStatus.values:
            raise InvalidProjectConfiguration("Invalid project status.")

        project.status = status

    if capture_mode is not None:
        _validate_capture_mode(capture_mode)
        project.capture_mode = capture_mode

    if retention_days is not None:
        _validate_retention_days(retention_days)
        project.retention_days = retention_days

    project.save(
        update_fields=(
            "name",
            "description",
            "status",
            "capture_mode",
            "retention_days",
            "updated_at",
        )
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="project.updated",
        resource_type="project",
        resource_id=project.id,
        context=audit_context,
        before_state=before_state,
        after_state=project_snapshot(project),
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
    capture_mode_override: str | None,
    retention_days_override: int | None,
    audit_context: AuditContext,
) -> Environment:
    """Create a deployment environment in an active project."""
    _require_project_resource_manager(
        actor=actor,
        organization=organization,
    )

    project = _get_locked_project(
        organization=organization,
        project_id=project_id,
    )

    if project.status != ResourceStatus.ACTIVE:
        raise ProjectInactive("New environments cannot be added to an archived project.")

    normalized_name = name.strip()

    if not normalized_name:
        raise InvalidEnvironmentConfiguration("Environment name cannot be empty.")

    if environment_type not in EnvironmentType.values:
        raise InvalidEnvironmentConfiguration("Invalid environment type.")

    _validate_environment_capture_mode(capture_mode_override)
    _validate_environment_retention_days(retention_days_override)

    slug = _build_available_environment_slug(
        project=project,
        name=normalized_name,
        requested_slug=requested_slug,
    )

    try:
        environment = Environment.objects.create(
            organization=organization,
            project=project,
            name=normalized_name,
            slug=slug,
            environment_type=environment_type,
            status=ResourceStatus.ACTIVE,
            capture_mode_override=capture_mode_override or "",
            retention_days_override=retention_days_override,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise EnvironmentConflict("An environment with this slug already exists in the project.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="environment.created",
        resource_type="environment",
        resource_id=environment.id,
        context=audit_context,
        after_state=environment_snapshot(environment),
        metadata={
            "created_automatically": False,
        },
    )

    return environment


@transaction.atomic
def update_environment(
    *,
    actor: User,
    organization: Organization,
    project_id: UUID | str,
    environment_id: UUID | str,
    name: str | None,
    environment_type: str | None,
    status: str | None,
    capture_mode_override_supplied: bool,
    capture_mode_override: str | None,
    retention_days_override_supplied: bool,
    retention_days_override: int | None,
    audit_context: AuditContext,
) -> Environment:
    """Update a project environment."""
    _require_project_resource_manager(
        actor=actor,
        organization=organization,
    )

    project = _get_locked_project(
        organization=organization,
        project_id=project_id,
    )

    environment = _get_locked_environment(
        organization=organization,
        project=project,
        environment_id=environment_id,
    )

    before_state = environment_snapshot(environment)

    if name is not None:
        normalized_name = name.strip()

        if not normalized_name:
            raise InvalidEnvironmentConfiguration("Environment name cannot be empty.")

        environment.name = normalized_name

    if environment_type is not None:
        if environment_type not in EnvironmentType.values:
            raise InvalidEnvironmentConfiguration("Invalid environment type.")

        environment.environment_type = environment_type

    if status is not None:
        if status not in ResourceStatus.values:
            raise InvalidEnvironmentConfiguration("Invalid environment status.")

        environment.status = status

    if capture_mode_override_supplied:
        _validate_environment_capture_mode(capture_mode_override)
        environment.capture_mode_override = capture_mode_override or ""

    if retention_days_override_supplied:
        _validate_environment_retention_days(retention_days_override)
        environment.retention_days_override = retention_days_override

    environment.save(
        update_fields=(
            "name",
            "environment_type",
            "status",
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
        after_state=environment_snapshot(environment),
    )

    return environment
