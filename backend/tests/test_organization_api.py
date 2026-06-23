"""Tests for organization APIs and tenant isolation."""

import pytest
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.organizations.constants import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
)
from agentproof_backend.apps.organizations.models import (
    MembershipRole,
)
from tests.organization_helpers import (
    add_member,
    create_test_organization,
    create_user,
)

pytestmark = pytest.mark.django_db


def authenticated_client(user: User) -> APIClient:
    """Create an authenticated DRF test client."""
    client = APIClient()
    client.force_login(user)
    return client


def set_active_organization(
    *,
    client: APIClient,
    organization_id: object,
) -> None:
    """Set the active tenant in a test session."""
    session = client.session
    session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization_id)
    session.save()


def test_create_organization_api_sets_active_tenant() -> None:
    user = create_user(
        email="owner@example.com",
    )
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/organizations/",
        {
            "name": "AgentProof Labs",
            "slug": "agentproof-labs",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["role"] == MembershipRole.OWNER
    assert client.session[ACTIVE_ORGANIZATION_SESSION_KEY] == response.json()["organization"]["id"]


def test_user_lists_only_own_organizations() -> None:
    first_user = create_user(
        email="first@example.com",
    )
    second_user = create_user(
        email="second@example.com",
    )

    first_organization, _membership = create_test_organization(
        owner=first_user,
        name="First Organization",
    )
    create_test_organization(
        owner=second_user,
        name="Second Organization",
    )

    client = authenticated_client(first_user)

    response = client.get(
        "/api/v1/organizations/",
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["organization"]["id"] == str(first_organization.id)


def test_path_organization_must_match_active_tenant() -> None:
    user = create_user(
        email="owner@example.com",
    )

    first_organization, _membership = create_test_organization(
        owner=user,
        name="First Organization",
    )
    second_organization, _membership = create_test_organization(
        owner=user,
        name="Second Organization",
    )

    client = authenticated_client(user)

    set_active_organization(
        client=client,
        organization_id=first_organization.id,
    )

    response = client.get(f"/api/v1/organizations/{second_organization.id}/")

    assert response.status_code == 403


def test_switch_requires_membership() -> None:
    first_user = create_user(
        email="first@example.com",
    )
    second_user = create_user(
        email="second@example.com",
    )

    organization, _membership = create_test_organization(
        owner=second_user,
    )

    client = authenticated_client(first_user)

    response = client.post(f"/api/v1/organizations/{organization.id}/switch/")

    assert response.status_code == 404


def test_viewer_cannot_create_invitation() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    viewer = create_user(
        email="viewer@example.com",
    )

    organization, _membership = create_test_organization(
        owner=owner,
    )

    add_member(
        organization=organization,
        user=viewer,
        role=MembershipRole.VIEWER,
    )

    client = authenticated_client(viewer)

    set_active_organization(
        client=client,
        organization_id=organization.id,
    )

    response = client.post(
        (f"/api/v1/organizations/{organization.id}/invitations/"),
        {
            "email": "new@example.com",
            "role": MembershipRole.DEVELOPER,
        },
        format="json",
    )

    assert response.status_code == 403


def test_member_list_is_tenant_scoped() -> None:
    first_owner = create_user(
        email="first-owner@example.com",
    )
    second_owner = create_user(
        email="second-owner@example.com",
    )

    first_organization, _membership = create_test_organization(
        owner=first_owner,
        name="First Organization",
    )

    create_test_organization(
        owner=second_owner,
        name="Second Organization",
    )

    client = authenticated_client(first_owner)

    set_active_organization(
        client=client,
        organization_id=first_organization.id,
    )

    response = client.get(f"/api/v1/organizations/{first_organization.id}/members/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["user"]["email"] == first_owner.email
