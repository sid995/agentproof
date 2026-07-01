"""Read focused API key queries"""

from uuid import UUID

from django.db.models import QuerySet

from agentproof_backend.apps.api_keys.exceptions import APIKeyNotFound
from agentproof_backend.apps.api_keys.models import APIKey
from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.models import Environment


def api_keys_for_environment(
    *,
    organization: Organization,
    environment: Environment,
) -> QuerySet[APIKey]:
    return APIKey.objects.filter(organization=organization, environment=environment).select_related(
        "organization", "project", "environment", "created_by"
    )


def get_api_key_for_organization(
    *,
    organization: Organization,
    api_key_id: UUID | str,
) -> APIKey:
    try:
        return APIKey.objects.select_related("organization", "project", "environment", "created_by").get(
            id=api_key_id, organization=organization
        )
    except APIKey.DoesNotExist as exc:
        raise APIKeyNotFound("The API key does not exist") from exc
