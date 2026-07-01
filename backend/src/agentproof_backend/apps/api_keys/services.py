"""State changing API key cuse cases"""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.api_keys.exceptions import (
    APIKeyAuthenticationFailed,
    APIKeyConflict,
    APIKeyNotFound,
    APIKeyPermissionDenied,
    InvalidAPIKeyConfiguration,
)
from agentproof_backend.apps.api_keys.models import APIKey, APIKeyScope
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.services import record_audit_event
from agentproof_backend.apps.organizations.models import Membership, MembershipRole, MembershipStatus, Organization
from agentproof_backend.apps.projects.models import Environment, ResourceStatus

KEY_PREFIX = "ap_live"
DEFAULT_SCOPE = APIKeyScope.TRACES_WRITE
MANAGER_ROLES = {MembershipRole.OWNER, MembershipRole.ADMINISTRATOR, MembershipRole.DEVELOPER}


@dataclass(frozen=True, slots=True)
class CreatedAPIKey:
    """Created API key plus the plaintext value shown once"""

    api_key: APIKey
    plaintext: str


@dataclass(frozen=True, slots=True)
class VerifiedAPIKey:
    """Authenticated API key context for SDK and ingestion requests"""

    api_key: APIKey
    organization_id: UUID
    project_id: UUID
    environment_id: UUID
    scopes: frozenset[str]


def api_key_snapshot(api_key: APIKey) -> dict[str, object]:
    """Serializable audit snapshot that deliberately excludes secrets"""

    return {
        "id": str(api_key.id),
        "organization_id": str(api_key.organization_id),
        "project_id": str(api_key.project_id),
        "environment_id": str(api_key.environment_id),
        "name": api_key.name,
        "prefix": api_key.prefix,
        "scopes": list(api_key.scopes),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "revoked_at": api_key.revoked_at.isoformat() if api_key.revoked_at else None,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
    }


def _require_manager(*, actor: User, organization: Organization) -> Membership:
    try:
        membership = Membership.objects.get(
            organization=organization,
            user=actor,
            status=MembershipStatus.ACTIVE,
        )
    except Membership.DoesNotExist as exc:
        raise APIKeyPermissionDenied("You are not an active organization member") from exc

    if membership.role not in MANAGER_ROLES:
        raise APIKeyPermissionDenied("Owner, administrator, or developer access is required")

    return membership


def _validate_scopes(scopes: Sequence[str]) -> list[str]:
    normalized = list(dict.fromkeys(scopes or [DEFAULT_SCOPE]))

    if not normalized:
        raise InvalidAPIKeyConfiguration("At least one scope is required")

    invalid = [scope for scope in normalized if scope not in APIKeyScope.values]
    if invalid:
        raise InvalidAPIKeyConfiguration("One of more API key scopes are invalid")

    return normalized


def _build_plaintext_key(*, prefix: str, secret: str) -> str:
    return f"{KEY_PREFIX}_{prefix}_{secret}"


def parse_plaintext_key(plaintext: str) -> tuple[str, str]:
    """Return public prefix and private secret from a presented key"""
    parts = plaintext.split("_", 3)

    if len(parts) != 4 or parts[0] != "ap" or parts[1] != "live":
        raise APIKeyAuthenticationFailed("Malformed API key")

    prefix = parts[2]
    secret = parts[3]

    if not prefix or not secret:
        raise APIKeyAuthenticationFailed("Malformed API key")

    return prefix, secret


def _generate_unique_parts() -> tuple[str, str, str]:
    prefix = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    secret = secrets.token_urlsafe(32)
    return prefix, secret, _build_plaintext_key(prefix=prefix, secret=secret)


@transaction.atomic
def create_api_key(
    *,
    actor: User,
    environment: Environment,
    name: str,
    scopes: Sequence[str],
    expires_at: datetime | None,
    audit_context: AuditContext,
) -> CreatedAPIKey:
    """Create an API key and return plaintext exactly once"""

    _require_manager(actor=actor, organization=environment.organization)

    normalized_name = name.strip()

    if not normalized_name:
        raise InvalidAPIKeyConfiguration("API key name cannot be empty")

    if environment.status != ResourceStatus.ACTIVE or environment.project.status != ResourceStatus.ACTIVE:
        raise InvalidAPIKeyConfiguration("API keys can only be created for active environments")

    normalized_scopes = _validate_scopes(scopes)

    for _attempt in range(5):
        prefix, secret, plaintext = _generate_unique_parts()

        if APIKey.objects.filter(prefix=prefix).exists():
            continue

        try:
            with transaction.atomic():
                api_key = APIKey.objects.create(
                    organization=environment.organization,
                    project=environment.project,
                    environment=environment,
                    name=normalized_name,
                    prefix=prefix,
                    key_hash=make_password(secret),
                    scopes=normalized_scopes,
                    created_by=actor,
                    expires_at=expires_at,
                )
        except IntegrityError:
            continue

        record_audit_event(
            organization=environment.organization,
            actor=actor,
            action="api_key.created",
            resource_type="api_key",
            resource_id=api_key.id,
            context=audit_context,
            after_state=api_key_snapshot(api_key),
        )
        return CreatedAPIKey(api_key=api_key, plaintext=plaintext)

    raise APIKeyConflict("Could not allocate a unique API key prefix.")


@transaction.atomic
def revoke_api_key(
    *,
    actor: User,
    organization: Organization,
    api_key_id: UUID | str,
    audit_context: AuditContext,
) -> APIKey:
    """Revoke an API key without deleting audit history"""
    _require_manager(actor=actor, organization=organization)

    try:
        api_key = APIKey.objects.select_for_update().get(id=api_key_id, organization=organization)
    except APIKey.DoesNotExist as exc:
        raise APIKeyNotFound("The API key does not exist") from exc

    before_state = api_key_snapshot(api_key)

    if api_key.revoked_at is None:
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=("revoked_at", "updated_at"))

        record_audit_event(
            organization=organization,
            actor=actor,
            action="api_key.revoked",
            resource_type="api_key",
            resource_id=api_key.id,
            context=audit_context,
            before_state=before_state,
            after_state=api_key_snapshot(api_key),
        )

    return api_key


def verify_api_key(
    *,
    plaintext: str,
    required_scope: str,
    environment_id: UUID | str | None = None,
) -> VerifiedAPIKey:
    """Validate a presented API key for one environment and scope."""
    prefix, secret = parse_plaintext_key(plaintext)

    try:
        api_key = APIKey.objects.select_related("organization", "project", "environment", "created_by").get(
            prefix=prefix
        )
    except APIKey.DoesNotExist as exc:
        raise APIKeyAuthenticationFailed("Invalid API key.") from exc

    if not check_password(secret, api_key.key_hash):
        raise APIKeyAuthenticationFailed("Invalid API key.")

    now = timezone.now()

    if api_key.revoked_at is not None:
        raise APIKeyAuthenticationFailed("API key has been revoked.")

    if api_key.expires_at is not None and api_key.expires_at <= now:
        raise APIKeyAuthenticationFailed("API key has expired.")

    if environment_id is not None and str(api_key.environment_id) != str(environment_id):
        raise APIKeyAuthenticationFailed("API key is not valid for this environment.")

    if required_scope not in api_key.scopes:
        raise APIKeyAuthenticationFailed("API key does not have the required scope.")

    return VerifiedAPIKey(
        api_key=api_key,
        organization_id=api_key.organization_id,
        project_id=api_key.project_id,
        environment_id=api_key.environment_id,
        scopes=frozenset(api_key.scopes),
    )
