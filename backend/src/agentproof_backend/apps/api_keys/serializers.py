"""API key serializers"""

from typing import Any

from rest_framework import serializers

from agentproof_backend.apps.api_keys.models import APIKey, APIKeyScope
from agentproof_backend.apps.api_keys.services import CreatedAPIKey


class APIKeySerializer(serializers.ModelSerializer[APIKey]):
    """API key representation that never exposes hash or plaintext"""

    class Meta:
        model = APIKey
        fields = (
            "id",
            "organization_id",
            "project_id",
            "environment_id",
            "name",
            "prefix",
            "scopes",
            "created_by_id",
            "created_at",
            "updated_at",
            "expires_at",
            "revoked_at",
            "last_used_at",
        )
        read_only_fields = fields


class APIKeyCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """API key creation request"""

    name = serializers.CharField(max_length=120, trim_whitespace=True)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=APIKeyScope.choices),
        required=False,
        allow_empty=False,
        default=[APIKeyScope.TRACES_WRITE],
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


class APIKeyCreationResponseSerializer(serializers.Serializer[CreatedAPIKey]):
    """Serialization response to API key creation"""

    api_key = serializers.CharField(read_only=True)
    record = APIKeySerializer(read_only=True)

    def to_representation(self, instance: CreatedAPIKey) -> dict[str, Any]:
        return {"api_key": instance.plaintext, "record": APIKeySerializer(instance.api_key).data}


class APIKeyAuthCheckSerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.CharField()
    organization_id = serializers.UUIDField()
    project_id = serializers.UUIDField()
    environment_id = serializers.UUIDField()
    scopes = serializers.ListField(child=serializers.CharField())
