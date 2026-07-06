"""Tests for environment API keys"""

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.api_keys.exceptions import (
    APIKeyAuthenticationFailed,
    APIKeyConflict,
    InvalidAPIKeyConfiguration,
)
from agentproof_backend.apps.api_keys.models import APIKey, APIKeyScope
from agentproof_backend.apps.api_keys.services import (
    create_api_key,
    parse_plaintext_key,
    revoke_api_key,
    verify_api_key,
)
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.models import AuditEvent
from agentproof_backend.apps.organizations.constants import ACTIVE_ORGANIZATION_SESSION_KEY
from agentproof_backend.apps.organizations.models import MembershipRole
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project, ResourceStatus
from agentproof_backend.apps.projects.services import create_project
from backend.tests.organization_helpers import add_member, create_test_organization, create_user

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-five-test",
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


def create_project_with_default_environment(*, actor: User, name: str = "Support Agent") -> tuple[Project, Environment]:
    organization, _membership = create_test_organization(owner=actor)
    result = create_project(
        actor=actor,
        organization=organization,
        name=name,
        requested_slug=None,
        description="Customer support workflow",
        capture_mode=CaptureMode.REDACTED,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.project, result.default_environment


def create_test_api_key(
    *,
    actor: User,
    environment: Environment,
    scopes: list[str] | None = None,
    expires_at: Any | None = None,
) -> tuple[APIKey, str]:
    result = create_api_key(
        actor=actor,
        environment=environment,
        name="Ingestion key",
        scopes=scopes or [APIKeyScope.TRACES_WRITE],
        expires_at=expires_at,
        audit_context=AUDIT_CONTEXT,
    )

    return result.api_key, result.plaintext


def test_create_api_key_persists_hash_not_plaintext() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)

    api_key, plaintext = create_test_api_key(actor=owner, environment=environment)
    prefix, secret = parse_plaintext_key(plaintext)

    api_key.refresh_from_db()

    assert plaintext.startswith("ap_live_")
    assert api_key.prefix == prefix
    assert api_key.key_hash != plaintext
    assert api_key.key_hash != secret
    assert check_password(secret, api_key.key_hash)
    assert APIKey.objects.filter(key_hash__contains=secret).exists() is False


def test_create_api_key_records_audit_event() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)

    api_key, _plaintext = create_test_api_key(actor=owner, environment=environment)

    assert AuditEvent.objects.filter(
        organization=environment.organization,
        action="api_key.created",
        resource_type="api_key",
        resource_id=str(api_key.id),
    ).exists()


def test_create_api_key_normalizes_duplicate_scopes() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)

    api_key, _plaintext = create_test_api_key(
        actor=owner,
        environment=environment,
        scopes=[APIKeyScope.TRACES_WRITE, APIKeyScope.TRACES_WRITE, APIKeyScope.TRACES_READ],
    )

    assert api_key.scopes == [APIKeyScope.TRACES_WRITE, APIKeyScope.TRACES_READ]


def test_create_api_key_rejects_inactive_environment() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    environment.status = ResourceStatus.ARCHIVED
    environment.save(update_fields=("status", "updated_at"))

    with pytest.raises(InvalidAPIKeyConfiguration):
        create_api_key(
            actor=owner,
            environment=environment,
            name="Archived key",
            scopes=[APIKeyScope.TRACES_WRITE],
            expires_at=None,
            audit_context=AUDIT_CONTEXT,
        )


def test_parse_plaintext_key_rejects_malformed_values() -> None:
    for plaintext in ("", "not-a-key", "ap_live_onlyprefix_", "ap_test_prefix_secret"):
        with pytest.raises(APIKeyAuthenticationFailed):
            parse_plaintext_key(plaintext)


def test_verify_api_key_accepts_valid_environment_and_scope() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    api_key, plaintext = create_test_api_key(actor=owner, environment=environment)

    verified = verify_api_key(
        plaintext=plaintext,
        required_scope=APIKeyScope.TRACES_WRITE,
        environment_id=environment.id,
    )

    assert verified.api_key == api_key
    assert verified.organization_id == environment.organization_id
    assert verified.project_id == environment.project_id
    assert verified.environment_id == environment.id
    assert APIKeyScope.TRACES_WRITE in verified.scopes


def test_verify_api_key_rejects_revoked_key() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    api_key, plaintext = create_test_api_key(actor=owner, environment=environment)

    revoke_api_key(
        actor=owner,
        organization=environment.organization,
        api_key_id=api_key.id,
        audit_context=AUDIT_CONTEXT,
    )

    with pytest.raises(APIKeyAuthenticationFailed):
        verify_api_key(
            plaintext=plaintext,
            required_scope=APIKeyScope.TRACES_WRITE,
            environment_id=environment.id,
        )


def test_verify_api_key_rejects_expired_key() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    _api_key, plaintext = create_test_api_key(
        actor=owner,
        environment=environment,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    with pytest.raises(APIKeyAuthenticationFailed):
        verify_api_key(
            plaintext=plaintext,
            required_scope=APIKeyScope.TRACES_WRITE,
            environment_id=environment.id,
        )


def test_verify_api_key_rejects_wrong_environment() -> None:
    owner = create_user(email="owner@example.com")
    project, first_environment = create_project_with_default_environment(actor=owner)
    second_environment = Environment.objects.create(
        organization=project.organization,
        project=project,
        name="Production",
        slug="production",
        environment_type="production",
        status="active",
        capture_mode_override="",
        retention_days_override=None,
        created_by=owner,
    )
    _api_key, plaintext = create_test_api_key(actor=owner, environment=first_environment)

    with pytest.raises(APIKeyAuthenticationFailed):
        verify_api_key(
            plaintext=plaintext,
            required_scope=APIKeyScope.TRACES_WRITE,
            environment_id=second_environment.id,
        )


def test_verify_api_key_rejects_wrong_scope() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    _api_key, plaintext = create_test_api_key(
        actor=owner,
        environment=environment,
        scopes=[APIKeyScope.TRACES_READ],
    )

    with pytest.raises(APIKeyAuthenticationFailed):
        verify_api_key(
            plaintext=plaintext,
            required_scope=APIKeyScope.TRACES_WRITE,
            environment_id=environment.id,
        )


def test_prefix_collision_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    first_key, _plaintext = create_test_api_key(actor=owner, environment=environment)

    generated_parts = [
        (first_key.prefix, "duplicate-secret", f"ap_live_{first_key.prefix}_duplicate-secret"),
        ("freshprefix1", "fresh-secret", "ap_live_freshprefix1_fresh-secret"),
    ]

    def fake_generate_unique_parts() -> tuple[str, str, str]:
        return generated_parts.pop(0)

    monkeypatch.setattr(
        "agentproof_backend.apps.api_keys.services._generate_unique_parts",
        fake_generate_unique_parts,
    )

    second = create_api_key(
        actor=owner,
        environment=environment,
        name="Retry key",
        scopes=[APIKeyScope.TRACES_WRITE],
        expires_at=None,
        audit_context=AUDIT_CONTEXT,
    )

    assert second.api_key.prefix == "freshprefix1"


def test_prefix_collision_fails_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    first_key, _plaintext = create_test_api_key(actor=owner, environment=environment)

    def fake_generate_unique_parts() -> tuple[str, str, str]:
        return first_key.prefix, "duplicate-secret", f"ap_live_{first_key.prefix}_duplicate-secret"

    monkeypatch.setattr(
        "agentproof_backend.apps.api_keys.services._generate_unique_parts",
        fake_generate_unique_parts,
    )

    with pytest.raises(APIKeyConflict):
        create_api_key(
            actor=owner,
            environment=environment,
            name="Retry key",
            scopes=[APIKeyScope.TRACES_WRITE],
            expires_at=None,
            audit_context=AUDIT_CONTEXT,
        )


def test_api_key_value_is_only_returned_on_create_api() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=environment.organization_id)

    create_response = client.post(
        f"/api/v1/environments/{environment.id}/api-keys/",
        {
            "name": "SDK key",
            "scopes": [APIKeyScope.TRACES_WRITE],
        },
        format="json",
    )
    list_response = client.get(f"/api/v1/environments/{environment.id}/api-keys/")

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["api_key"].startswith("ap_live_")
    assert "key_hash" not in create_response.json()["record"]
    assert "api_key" not in list_response.json()[0]
    assert "key_hash" not in list_response.json()[0]


def test_viewer_can_list_but_cannot_create_api_key() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    add_member(organization=environment.organization, user=viewer, role=MembershipRole.VIEWER)
    create_test_api_key(actor=owner, environment=environment)

    client = authenticated_client(viewer)
    set_active_organization(client=client, organization_id=environment.organization_id)

    list_response = client.get(f"/api/v1/environments/{environment.id}/api-keys/")
    create_response = client.post(
        f"/api/v1/environments/{environment.id}/api-keys/",
        {"name": "Viewer key"},
        format="json",
    )

    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()) == 1
    assert create_response.status_code == 403


def test_revoke_api_key_api_blocks_future_authentication() -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    api_key, plaintext = create_test_api_key(actor=owner, environment=environment)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=environment.organization_id)

    response = client.post(f"/api/v1/api-keys/{api_key.id}/revoke/")

    assert response.status_code == 200
    api_key.refresh_from_db()
    assert api_key.revoked_at is not None

    with pytest.raises(APIKeyAuthenticationFailed):
        verify_api_key(
            plaintext=plaintext,
            required_scope=APIKeyScope.TRACES_WRITE,
            environment_id=environment.id,
        )


def test_auth_check_endpoint_accepts_valid_bearer_key(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = create_user(email="owner@example.com")
    _project, environment = create_project_with_default_environment(actor=owner)
    _api_key, plaintext = create_test_api_key(actor=owner, environment=environment)
    client = APIClient()

    monkeypatch.setattr(
        "agentproof_backend.apps.api_keys.authentication.update_api_key_last_used.delay",
        lambda _api_key_id: None,
    )

    response = client.post(
        f"/api/v1/environments/{environment.id}/auth-check/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {plaintext}",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment_id"] == str(environment.id)


def test_auth_check_endpoint_rejects_wrong_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = create_user(email="owner@example.com")
    project, first_environment = create_project_with_default_environment(actor=owner)
    second_environment = Environment.objects.create(
        organization=project.organization,
        project=project,
        name="Production",
        slug="production",
        environment_type="production",
        status="active",
        capture_mode_override="",
        retention_days_override=None,
        created_by=owner,
    )
    _api_key, plaintext = create_test_api_key(actor=owner, environment=first_environment)
    client = APIClient()

    monkeypatch.setattr(
        "agentproof_backend.apps.api_keys.authentication.update_api_key_last_used.delay",
        lambda _api_key_id: None,
    )

    response = client.post(
        f"/api/v1/environments/{second_environment.id}/auth-check/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {plaintext}",
    )

    assert response.status_code == 403
