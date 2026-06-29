"""Project and environment API serializers."""

from typing import Any

from rest_framework import serializers

from agentproof_backend.apps.projects.models import (
    MAX_RETENTION_DAYS,
    MIN_RETENTION_DAYS,
    CaptureMode,
    Environment,
    EnvironmentType,
    Project,
    ResourceStatus,
)
from agentproof_backend.apps.projects.services import CreatedProject


class ProjectSerializer(serializers.ModelSerializer[Project]):
    """Project API representation."""

    class Meta:
        model = Project
        fields = (
            "id",
            "organization_id",
            "name",
            "slug",
            "description",
            "status",
            "capture_mode",
            "retention_days",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Project creation request."""

    name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )
    slug = serializers.SlugField(
        max_length=63,
        required=False,
        allow_unicode=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    capture_mode = serializers.ChoiceField(
        choices=CaptureMode.choices,
        default=CaptureMode.REDACTED,
    )
    retention_days = serializers.IntegerField(
        min_value=MIN_RETENTION_DAYS,
        max_value=MAX_RETENTION_DAYS,
        default=30,
    )


class ProjectUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """Mutable project configuration."""

    name = serializers.CharField(
        max_length=150,
        required=False,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    status = serializers.ChoiceField(
        choices=ResourceStatus.choices,
        required=False,
    )
    capture_mode = serializers.ChoiceField(
        choices=CaptureMode.choices,
        required=False,
    )
    retention_days = serializers.IntegerField(
        min_value=MIN_RETENTION_DAYS,
        max_value=MAX_RETENTION_DAYS,
        required=False,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide at least one project field.")

        return attrs


class EnvironmentSerializer(serializers.ModelSerializer[Environment]):
    """Environment API representation."""

    project_id = serializers.UUIDField(read_only=True)
    effective_capture_mode = serializers.CharField(read_only=True)
    effective_retention_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Environment
        fields = (
            "id",
            "organization_id",
            "project_id",
            "name",
            "slug",
            "environment_type",
            "status",
            "capture_mode_override",
            "retention_days_override",
            "effective_capture_mode",
            "effective_retention_days",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectCreationResponseSerializer(serializers.Serializer[CreatedProject]):
    """Project creation response with default environment."""

    project = ProjectSerializer(read_only=True)
    default_environment = EnvironmentSerializer(read_only=True)


class EnvironmentCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Environment creation request."""

    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    slug = serializers.SlugField(
        max_length=63,
        required=False,
        allow_unicode=True,
    )
    environment_type = serializers.ChoiceField(
        choices=EnvironmentType.choices,
        default=EnvironmentType.CUSTOM,
    )
    capture_mode_override = serializers.ChoiceField(
        choices=CaptureMode.choices,
        required=False,
        allow_null=True,
        default=None,
    )
    retention_days_override = serializers.IntegerField(
        min_value=MIN_RETENTION_DAYS,
        max_value=MAX_RETENTION_DAYS,
        required=False,
        allow_null=True,
        default=None,
    )


class EnvironmentUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """Mutable environment configuration."""

    name = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    environment_type = serializers.ChoiceField(
        choices=EnvironmentType.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=ResourceStatus.choices,
        required=False,
    )
    capture_mode_override = serializers.ChoiceField(
        choices=CaptureMode.choices,
        required=False,
        allow_null=True,
    )
    retention_days_override = serializers.IntegerField(
        min_value=MIN_RETENTION_DAYS,
        max_value=MAX_RETENTION_DAYS,
        required=False,
        allow_null=True,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide at least one environment field.")

        return attrs
