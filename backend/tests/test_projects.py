"""Tests for project and environment tenancy."""

from typing import Any

import pytest
from django.db import IntegrityError
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.models import AuditEvent
from agentproof_backend.apps.organizations.constants import ACTIVE_ORGANIZATION_SESSION_KEY
from agentproof_backend.apps.organizations.models import MembershipRole
from agentproof_backend.apps.projects.exceptions import ProjectPermissionDenied
from agentproof_backend.apps.projects.models import CaptureMode, Environment, EnvironmentType, Project
from agentproof_backend.apps.projects.services import (
    create_environment,
    create_project,
    update_environment,
    update_project,
)
from tests.organization_helpers import add_member, create_test_organization, create_user

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-four-test",
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


def create_test_project(
    *,
    actor: User,
    organization: Any,
    name: str = "Support Agent",
    slug: str = "support-agent",
) -> Project:
    return create_project(
        actor=actor,
        organization=organization,
        name=name,
        requested_slug=slug,
        description="Customer support workflow",
        capture_mode=CaptureMode.REDACTED,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    ).project


def create_test_environment(
    *,
    actor: User,
    organization: Any,
    project: Project,
    name: str = "Production",
    slug: str = "production",
) -> Environment:
    return create_environment(
        actor=actor,
        organization=organization,
        project_id=project.id,
        name=name,
        requested_slug=slug,
        environment_type=EnvironmentType.PRODUCTION,
        capture_mode_override=None,
        retention_days_override=None,
        audit_context=AUDIT_CONTEXT,
    )


def test_owner_can_create_project_and_audit_event() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)

    project = create_test_project(actor=owner, organization=organization)

    assert project.organization == organization
    assert project.slug == "support-agent"
    assert project.capture_mode == CaptureMode.REDACTED
    assert project.retention_days == 30
    assert AuditEvent.objects.filter(
        organization=organization,
        action="project.created",
        resource_id=str(project.id),
    ).exists()


def test_developer_cannot_create_project() -> None:
    owner = create_user(email="owner@example.com")
    developer = create_user(email="developer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    add_member(organization=organization, user=developer, role=MembershipRole.DEVELOPER)

    with pytest.raises(ProjectPermissionDenied):
        create_test_project(
            actor=developer,
            organization=organization,
            name="Developer Project",
            slug="developer-project",
        )


def test_viewer_cannot_create_project() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    add_member(organization=organization, user=viewer, role=MembershipRole.VIEWER)

    with pytest.raises(ProjectPermissionDenied):
        create_test_project(actor=viewer, organization=organization)


def test_project_slug_can_repeat_across_organizations() -> None:
    first_owner = create_user(email="first-owner@example.com")
    second_owner = create_user(email="second-owner@example.com")
    first_organization, _membership = create_test_organization(owner=first_owner, name="First Org")
    second_organization, _membership = create_test_organization(owner=second_owner, name="Second Org")

    first_project = create_test_project(actor=first_owner, organization=first_organization, slug="shared")
    second_project = create_test_project(actor=second_owner, organization=second_organization, slug="shared")

    assert first_project.slug == second_project.slug
    assert first_project.organization != second_project.organization


def test_project_slug_conflicts_get_available_suffix_inside_organization() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    first_project = create_test_project(actor=owner, organization=organization, slug="duplicate")
    second_project = create_test_project(
        actor=owner,
        organization=organization,
        name="Duplicate",
        slug="duplicate",
    )

    assert first_project.slug == "duplicate"
    assert second_project.slug.startswith("duplicate-")


def test_project_update_records_audit_event() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)

    updated = update_project(
        actor=owner,
        organization=organization,
        project_id=project.id,
        name="Updated Agent",
        description="Updated description",
        status=None,
        capture_mode=CaptureMode.FULL,
        retention_days=14,
        audit_context=AUDIT_CONTEXT,
    )

    assert updated.name == "Updated Agent"
    assert updated.capture_mode == CaptureMode.FULL
    assert updated.retention_days == 14
    assert AuditEvent.objects.filter(
        organization=organization,
        action="project.updated",
        resource_id=str(project.id),
    ).exists()


def test_project_list_api_is_tenant_scoped() -> None:
    first_owner = create_user(email="first-owner@example.com")
    second_owner = create_user(email="second-owner@example.com")
    first_organization, _membership = create_test_organization(owner=first_owner, name="First Org")
    second_organization, _membership = create_test_organization(owner=second_owner, name="Second Org")
    first_project = create_test_project(actor=first_owner, organization=first_organization, name="First", slug="first")
    create_test_project(actor=second_owner, organization=second_organization, name="Second", slug="second")

    client = authenticated_client(first_owner)
    set_active_organization(client=client, organization_id=first_organization.id)

    response = client.get("/api/v1/projects/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == str(first_project.id)


def test_cross_tenant_project_detail_is_not_visible() -> None:
    first_owner = create_user(email="first-owner@example.com")
    second_owner = create_user(email="second-owner@example.com")
    first_organization, _membership = create_test_organization(owner=first_owner, name="First Org")
    second_organization, _membership = create_test_organization(owner=second_owner, name="Second Org")
    second_project = create_test_project(actor=second_owner, organization=second_organization)

    client = authenticated_client(first_owner)
    set_active_organization(client=client, organization_id=first_organization.id)

    response = client.get(f"/api/v1/projects/{second_project.id}/")

    assert response.status_code == 404


def test_project_create_api_derives_organization_from_active_tenant() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.post(
        "/api/v1/projects/",
        {
            "name": "Billing Agent",
            "slug": "billing-agent",
            "description": "Billing workflow",
            "capture_mode": CaptureMode.METADATA_ONLY,
            "retention_days": 7,
        },
        format="json",
    )

    assert response.status_code == 201
    response_data = response.json()
    project = Project.objects.get(id=response_data["project"]["id"])
    assert project.organization == organization
    assert response_data["default_environment"]["project_id"] == str(project.id)
    assert response_data["default_environment"]["slug"] == "development"


def test_viewer_can_read_but_not_create_project_api() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    add_member(organization=organization, user=viewer, role=MembershipRole.VIEWER)

    client = authenticated_client(viewer)
    set_active_organization(client=client, organization_id=organization.id)

    read_response = client.get(f"/api/v1/projects/{project.id}/")
    create_response = client.post(
        "/api/v1/projects/",
        {"name": "Viewer Project", "slug": "viewer-project"},
        format="json",
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403


def test_developer_can_create_environment() -> None:
    owner = create_user(email="owner@example.com")
    developer = create_user(email="developer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    add_member(organization=organization, user=developer, role=MembershipRole.DEVELOPER)
    project = create_test_project(actor=owner, organization=organization)

    environment = create_test_environment(actor=developer, organization=organization, project=project)

    assert environment.organization == organization
    assert environment.project == project
    assert environment.environment_type == EnvironmentType.PRODUCTION
    assert AuditEvent.objects.filter(
        organization=organization,
        action="environment.created",
        resource_id=str(environment.id),
    ).exists()


def test_environment_slug_conflicts_get_available_suffix_per_project() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    first_project = create_test_project(actor=owner, organization=organization, name="First", slug="first")
    second_project = create_test_project(actor=owner, organization=organization, name="Second", slug="second")

    first_environment = create_test_environment(
        actor=owner,
        organization=organization,
        project=first_project,
        slug="production",
    )
    duplicate_environment = create_test_environment(
        actor=owner,
        organization=organization,
        project=first_project,
        name="Duplicate Production",
        slug="production",
    )

    second_environment = create_test_environment(
        actor=owner,
        organization=organization,
        project=second_project,
        slug="production",
    )
    assert first_environment.slug == "production"
    assert duplicate_environment.slug.startswith("production-")
    assert second_environment.slug == "production"


def test_environment_cannot_point_to_mismatched_organization_at_database_level() -> None:
    first_owner = create_user(email="first-owner@example.com")
    second_owner = create_user(email="second-owner@example.com")
    first_organization, _membership = create_test_organization(owner=first_owner, name="First Org")
    second_organization, _membership = create_test_organization(owner=second_owner, name="Second Org")
    second_project = create_test_project(actor=second_owner, organization=second_organization)

    with pytest.raises(ValueError, match="Environment organization must match"):
        Environment.objects.create(
            organization=first_organization,
            project=second_project,
            name="Invalid",
            slug="invalid",
            environment_type=EnvironmentType.CUSTOM,
            created_by=first_owner,
        )


def test_environment_cannot_be_created_for_cross_tenant_project_api() -> None:
    first_owner = create_user(email="first-owner@example.com")
    second_owner = create_user(email="second-owner@example.com")
    first_organization, _membership = create_test_organization(owner=first_owner, name="First Org")
    second_organization, _membership = create_test_organization(owner=second_owner, name="Second Org")
    second_project = create_test_project(actor=second_owner, organization=second_organization)

    client = authenticated_client(first_owner)
    set_active_organization(client=client, organization_id=first_organization.id)

    response = client.post(
        f"/api/v1/projects/{second_project.id}/environments/",
        {
            "name": "Production",
            "slug": "production",
            "environment_type": EnvironmentType.PRODUCTION,
        },
        format="json",
    )

    assert response.status_code == 404


def test_environment_list_api_is_scoped_to_project() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    first_project = create_test_project(actor=owner, organization=organization, name="First", slug="first")
    second_project = create_test_project(actor=owner, organization=organization, name="Second", slug="second")
    first_environment = create_test_environment(actor=owner, organization=organization, project=first_project)
    create_test_environment(
        actor=owner,
        organization=organization,
        project=second_project,
        name="Staging",
        slug="staging",
    )

    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/api/v1/projects/{first_project.id}/environments/")

    assert response.status_code == 200
    response_environment_ids = {environment["id"] for environment in response.json()}
    assert str(first_environment.id) in response_environment_ids
    assert all(environment["project_id"] == str(first_project.id) for environment in response.json())


def test_environment_create_api_returns_effective_configuration() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.post(
        f"/api/v1/projects/{project.id}/environments/",
        {
            "name": "Development",
            "slug": "development",
            "environment_type": EnvironmentType.DEVELOPMENT,
            "capture_mode_override": CaptureMode.FULL,
            "retention_days_override": 3,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["effective_capture_mode"] == CaptureMode.FULL
    assert response.json()["effective_retention_days"] == 3


def test_environment_update_records_audit_event() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    environment = create_test_environment(actor=owner, organization=organization, project=project)

    updated = update_environment(
        actor=owner,
        organization=organization,
        project_id=project.id,
        environment_id=environment.id,
        name="Prod",
        environment_type=EnvironmentType.PRODUCTION,
        status=None,
        capture_mode_override_supplied=True,
        capture_mode_override=CaptureMode.FULL,
        retention_days_override_supplied=True,
        retention_days_override=7,
        audit_context=AUDIT_CONTEXT,
    )

    assert updated.name == "Prod"
    assert updated.capture_mode_override == CaptureMode.FULL
    assert updated.retention_days_override == 7
    assert AuditEvent.objects.filter(
        organization=organization,
        action="environment.updated",
        resource_id=str(environment.id),
    ).exists()


def test_environment_update_api_can_clear_retention_override() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    environment = create_environment(
        actor=owner,
        organization=organization,
        project_id=project.id,
        name="Development",
        requested_slug="development",
        environment_type=EnvironmentType.DEVELOPMENT,
        capture_mode_override=CaptureMode.FULL,
        retention_days_override=5,
        audit_context=AUDIT_CONTEXT,
    )

    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.patch(
        f"/api/v1/environments/{environment.id}/",
        {"retention_days_override": None},
        format="json",
    )

    assert response.status_code == 200
    environment.refresh_from_db()
    assert environment.retention_days_override is None
    assert response.json()["effective_retention_days"] == project.retention_days


def test_viewer_can_read_but_not_update_environment_api() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    environment = create_test_environment(actor=owner, organization=organization, project=project)
    add_member(organization=organization, user=viewer, role=MembershipRole.VIEWER)

    client = authenticated_client(viewer)
    set_active_organization(client=client, organization_id=organization.id)

    read_response = client.get(f"/api/v1/environments/{environment.id}/")
    update_response = client.patch(
        f"/api/v1/environments/{environment.id}/",
        {"name": "Blocked"},
        format="json",
    )

    assert read_response.status_code == 200
    assert update_response.status_code == 403


def test_database_prevents_duplicate_environment_slug_inside_project() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    create_test_environment(actor=owner, organization=organization, project=project, slug="production")

    with pytest.raises(IntegrityError):
        Environment.objects.create(
            organization=organization,
            project=project,
            name="Duplicate",
            slug="production",
            environment_type=EnvironmentType.PRODUCTION,
            created_by=owner,
        )


def test_project_list_page_renders_projects() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)

    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get("/projects/")

    assert response.status_code == 200
    assert project.name.encode() in response.content


def test_project_detail_page_renders_environments() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    environment = create_test_environment(actor=owner, organization=organization, project=project)

    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/projects/{project.id}/")

    assert response.status_code == 200
    assert environment.name.encode() in response.content


def test_environment_detail_page_renders_effective_settings() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project = create_test_project(actor=owner, organization=organization)
    environment = create_test_environment(actor=owner, organization=organization, project=project)

    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/projects/environments/{environment.id}/")

    assert response.status_code == 200
    assert b"Effective capture" in response.content
    assert b"Effective retention" in response.content


def test_viewer_project_list_page_hides_create_form() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    add_member(organization=organization, user=viewer, role=MembershipRole.VIEWER)

    client = authenticated_client(viewer)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get("/projects/")

    assert response.status_code == 200
    assert b"Create project" not in response.content
