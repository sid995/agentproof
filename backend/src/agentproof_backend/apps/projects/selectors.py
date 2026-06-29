"""Read-focused project and environment queries."""

from uuid import UUID

from django.db.models import QuerySet

from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.exceptions import (
    EnvironmentNotFound,
    ProjectNotFound,
)
from agentproof_backend.apps.projects.models import (
    Environment,
    Project,
)


def projects_for_organization(
    *,
    organization: Organization,
) -> QuerySet[Project]:
    """Return projects belonging to one organization."""
    return (
        Project.objects.filter(
            organization=organization,
        )
        .select_related(
            "organization",
            "created_by",
        )
        .prefetch_related("environments")
        .order_by(
            "name",
            "id",
        )
    )


def get_project_for_organization(
    *,
    organization: Organization,
    project_id: UUID | str,
) -> Project:
    """Return one project belonging to an organization."""
    try:
        return Project.objects.select_related(
            "organization",
            "created_by",
        ).get(
            id=project_id,
            organization=organization,
        )
    except Project.DoesNotExist as exc:
        raise ProjectNotFound("The project does not exist.") from exc


def environments_for_project(
    *,
    organization: Organization,
    project: Project,
) -> QuerySet[Environment]:
    """Return environments belonging to one tenant project."""
    return (
        Environment.objects.filter(
            organization=organization,
            project=project,
        )
        .select_related(
            "organization",
            "project",
            "created_by",
        )
        .order_by(
            "name",
            "id",
        )
    )


def get_environment_for_organization(
    *,
    organization: Organization,
    environment_id: UUID | str,
) -> Environment:
    try:
        return Environment.objects.select_related("organization", "project", "created_by").get(
            id=environment_id, organization=organization
        )
    except Environment.DoesNotExist as exc:
        raise EnvironmentNotFound("The environment does not exist.") from exc


def get_environment_for_project(
    *,
    organization: Organization,
    project: Project,
    environment_id: UUID | str,
) -> Environment:
    """Return one environment from one tenant project."""
    try:
        return Environment.objects.select_related(
            "organization",
            "project",
            "created_by",
        ).get(
            id=environment_id,
            organization=organization,
            project=project,
        )
    except Environment.DoesNotExist as exc:
        raise EnvironmentNotFound("The environment does not exist.") from exc
