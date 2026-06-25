"""Project API serializers."""

from typing import Any

from rest_framework import serializers

from agentproof_backend.apps.projects.models import CaptureMode, Environment, EnvironmentType, Project


class ProjectSerializer(serializers.ModelSerializer[Project]):
    """Project response representation."""

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "capture_mode",
            "retention_days",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProjectCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Create-project request."""

    name = serializers.CharField(max_length=150, trim_whitespace=True)
    slug = serializers.CharField(max_length=63, required=False, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    capture_mode = serializers.ChoiceField(choices=CaptureMode.choices, default=CaptureMode.REDACTED)
    retention_days = serializers.IntegerField(min_value=1, default=30)


class ProjectUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """Update-project request."""

    name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    capture_mode = serializers.ChoiceField(choices=CaptureMode.choices, required=False)
    retention_days = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide at least one project field.")
        return attrs


class EnvironmentSerializer(serializers.ModelSerializer[Environment]):
    """Environment response representation."""

    project_id = serializers.UUIDField(read_only=True)
    effective_capture_mode = serializers.SerializerMethodField()
    effective_retention_days = serializers.SerializerMethodField()

    class Meta:
        model = Environment
        fields = (
            "id",
            "project_id",
            "name",
            "slug",
            "environment_type",
            "capture_mode_override",
            "retention_days_override",
            "effective_capture_mode",
            "effective_retention_days",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @staticmethod
    def get_effective_capture_mode(obj: Environment) -> str:
        return obj.capture_mode_override or obj.project.capture_mode

    @staticmethod
    def get_effective_retention_days(obj: Environment) -> int:
        return obj.retention_days_override or obj.project.retention_days


class EnvironmentCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Create-environment request."""

    name = serializers.CharField(max_length=150, trim_whitespace=True)
    slug = serializers.CharField(max_length=63, required=False, allow_blank=False, trim_whitespace=True)
    environment_type = serializers.ChoiceField(choices=EnvironmentType.choices, default=EnvironmentType.DEVELOPMENT)
    capture_mode_override = serializers.ChoiceField(
        choices=CaptureMode.choices,
        required=False,
        allow_blank=True,
        default="",
    )
    retention_days_override = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class EnvironmentUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """Update-environment request."""

    name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    environment_type = serializers.ChoiceField(choices=EnvironmentType.choices, required=False)
    capture_mode_override = serializers.ChoiceField(choices=CaptureMode.choices, required=False, allow_blank=True)
    retention_days_override = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide at least one environment field.")
        return attrs
