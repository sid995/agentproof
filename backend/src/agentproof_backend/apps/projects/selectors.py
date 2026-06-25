"""Tenant scoped project queries"""

from uuid import UUID

from django.db.models import QuerySet

from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.exceptions import EnvironmentNotFound, ProjectNotFound
from agentproof_backend.apps.projects.models import Environment, Project


def projects_for_organization(*, organization: Organization) -> QuerySet[Project]:
    """Return projects for one organization"""

    return Project.objects.filter(organization=organization).order_by("name")


def get_project_for_organization(
    *,
    organization: Organization,
    project_id: UUID | str,
) -> Project:
    """Return one project scoped to an organization"""
    try:
        return projects_for_organization(organization=organization).get(id=project_id)
    except Project.DoesNotExist as exc:
        raise ProjectNotFound("The project does not exist.") from exc


def environments_for_project(*, project: Project) -> QuerySet[Environment]:
    """Return environments for one scoped project."""

    return Environment.objects.filter(
        organization=project.organization,
        project=project,
    ).order_by("name")


def get_environment_for_organization(
    *,
    organization: Organization,
    environment_id: UUID | str,
) -> Environment:
    """Return one environment scoped to an organization."""

    try:
        return (
            Environment.objects.select_related("project", "organization")
            .filter(organization=organization)
            .get(id=environment_id)
        )
    except Environment.DoesNotExist as exc:
        raise EnvironmentNotFound("The environment does not exist.") from exc
