"""Project and environment database models."""

from collections.abc import Iterable
from typing import ClassVar

from django.db import models
from django.db.models import Q
from django.db.models.base import ModelBase
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel
from agentproof_backend.apps.organizations.models import Organization

MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3_650


class ResourceStatus(models.TextChoices):
    """Lifecycle state for projects and environments."""

    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class CaptureMode(models.TextChoices):
    """Telemetry content-capture policy."""

    METADATA_ONLY = "metadata_only", "Metadata only"
    REDACTED = "redacted", "Redacted"
    FULL = "full", "Full"


class EnvironmentType(models.TextChoices):
    """Recognized deployment environment categories."""

    DEVELOPMENT = "development", "Development"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"
    CUSTOM = "custom", "Custom"


class Project(TimeStampedUUIDModel):
    """An AI application owned by an organization."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(
        max_length=150,
    )
    slug = models.SlugField(
        max_length=63,
        allow_unicode=True,
    )
    description = models.TextField(
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ResourceStatus.choices,
        default=ResourceStatus.ACTIVE,
        db_index=True,
    )

    capture_mode = models.CharField(
        max_length=20,
        choices=CaptureMode.choices,
        default=CaptureMode.REDACTED,
    )
    retention_days = models.PositiveSmallIntegerField(
        default=30,
    )

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_projects",
        null=False,
        blank=True,
    )

    class Meta:
        ordering = (
            "name",
            "id",
        )
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(
                fields=(
                    "organization",
                    "slug",
                ),
                name="unique_project_slug_per_org",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=ResourceStatus.values,
                ),
                name="project_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    capture_mode__in=CaptureMode.values,
                ),
                name="project_capture_mode_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    retention_days__gte=MIN_RETENTION_DAYS,
                    retention_days__lte=MAX_RETENTION_DAYS,
                ),
                name="project_retention_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=(
                    "organization",
                    "status",
                    "name",
                ),
                name="project_org_status_idx",
            ),
            models.Index(
                fields=(
                    "organization",
                    "created_at",
                ),
                name="project_org_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.name}"


class Environment(TimeStampedUUIDModel):
    """A deployment context belonging to one project."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="environments",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="environments",
    )

    name = models.CharField(
        max_length=100,
    )
    slug = models.SlugField(
        max_length=63,
        allow_unicode=True,
    )
    environment_type = models.CharField(
        max_length=20,
        choices=EnvironmentType.choices,
        default=EnvironmentType.CUSTOM,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ResourceStatus.choices,
        default=ResourceStatus.ACTIVE,
        db_index=True,
    )

    capture_mode_override = models.CharField(
        max_length=20,
        choices=CaptureMode.choices,
        blank=True,
    )
    retention_days_override = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_environments",
        null=False,
        blank=True,
    )

    class Meta:
        ordering = (
            "project__name",
            "name",
            "id",
        )
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(
                fields=(
                    "project",
                    "slug",
                ),
                name="unique_environment_slug_per_project",
            ),
            models.CheckConstraint(
                condition=Q(
                    environment_type__in=EnvironmentType.values,
                ),
                name="environment_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=ResourceStatus.values,
                ),
                name="environment_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(capture_mode_override="")
                    | Q(capture_mode_override__isnull=True)
                    | Q(capture_mode_override__in=CaptureMode.values)
                ),
                name="environment_capture_override_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(retention_days_override__isnull=True)
                    | Q(
                        retention_days_override__gte=MIN_RETENTION_DAYS,
                        retention_days_override__lte=MAX_RETENTION_DAYS,
                    )
                ),
                name="environment_retention_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=(
                    "organization",
                    "status",
                ),
                name="environment_org_status_idx",
            ),
            models.Index(
                fields=(
                    "project",
                    "status",
                    "environment_type",
                ),
                name="environment_project_idx",
            ),
        ]

    @property
    def effective_capture_mode(self) -> str:
        """Return the environment's resolved capture mode."""
        return self.capture_mode_override or self.project.capture_mode

    @property
    def effective_retention_days(self) -> int:
        """Return the environment's resolved retention period."""
        return self.retention_days_override or self.project.retention_days

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.project_id is not None and self.organization_id != self.project.organization_id:
            raise ValueError("Environment organization must match the parent project organization.")

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.project.name} / {self.name}"
