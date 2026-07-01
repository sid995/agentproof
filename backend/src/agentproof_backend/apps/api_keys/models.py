"""Environment-scoped API key models."""

from typing import ClassVar

from django.db import models
from django.db.models import Q
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel


class APIKeyScope(models.TextChoices):
    """Allowed API key capabilities."""

    TRACES_WRITE = "traces:write", "Write traces"
    TRACES_READ = "traces:read", "Read traces"
    EVALUATIONS_RUN = "evaluations:run", "Run evaluations"
    DATASETS_READ = "datasets:read", "Read datasets"
    CI_READ = "ci:read", "Read CI data"


class APIKey(TimeStampedUUIDModel):
    """A hashed secret that authenticates SDK and ingestion requests."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="api_keys")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="api_keys")
    environment = models.ForeignKey("projects.Environment", on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=32, unique=True, db_index=True)
    key_hash = models.CharField(max_length=256)
    scopes = models.JSONField(default=list)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_api_keys")
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.CheckConstraint(condition=~Q(name=""), name="api_key_name_not_empty"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("environment", "revoked_at"), name="api_key_env_revoked_idx"),
            models.Index(fields=("organization", "created_at"), name="api_key_org_created_idx"),
        ]

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def __str__(self) -> str:
        return f"{self.environment} / {self.name}"
