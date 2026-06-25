"""Project and environment database models"""

from typing import ClassVar

from django.db import models
from django.db.models import Q

from agentproof_backend.apps.common.models import TimeStampedUUIDModel


class CaptureMode(models.TextChoices):
    """Telemetry capture modes."""

    METADATA_ONLY = "metadata_only", "Metadata only"
    REDACTED = "redacted", "Redacted"
    FULL = "full", "Full"


class EnvironmentType(models.TextChoices):
    """Supported environment types."""

    DEVELOPMENT = "development", "Development"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"
    CUSTOM = "custom", "Custom"


class Project(TimeStampedUUIDModel):
    """An AI application or service owned by an organization"""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=63)
    description = models.TextField(blank=True)
    capture_mode = models.CharField(
        max_length=32,
        choices=CaptureMode,
        default=CaptureMode.REDACTED,
    )
    retention_days = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="unique_project_slug_per_org",
            ),
            models.CheckConstraint(
                condition=Q(capture_mode__in=CaptureMode.values),
                name="project_capture_mode_valid",
            ),
            models.CheckConstraint(
                condition=Q(retention_days__gte=1),
                name="project_retention_days_positive",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "slug"), name="project_org_slug_idx"),
            models.Index(fields=("organization", "name"), name="project_org_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.name})"


class Environment(TimeStampedUUIDModel):
    """A deploy/runtime environment belonging to one project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="environments",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="environments",
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=63)
    environment_type = models.CharField(
        max_length=32,
        choices=EnvironmentType,
        default=EnvironmentType.DEVELOPMENT,
    )
    capture_mode_override = models.CharField(
        max_length=32,
        choices=CaptureMode,
        blank=True,
    )
    retention_days_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("project__name", "name")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("project", "slug"),
                name="unique_environment_slug_per_project",
            ),
            models.CheckConstraint(
                condition=Q(environment_type__in=EnvironmentType.values),
                name="environment_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(capture_mode_override="") | Q(capture_mode_override__in=CaptureMode.values),
                name="environment_capture_override_valid",
            ),
            models.CheckConstraint(
                condition=Q(retention_days_override__isnull=True) | Q(retention_days_override__gte=1),
                name="environment_retention_override_positive",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "slug"), name="env_org_slug_idx"),
            models.Index(fields=("project", "slug"), name="env_project_slug_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.project.name})"
