"""Append-only audit database models."""

from typing import Any, ClassVar

from django.conf import settings
from django.db import models

from agentproof_backend.apps.common.models import UUIDModel


class AuditEventQuerySet(models.QuerySet["AuditEvent"]):
    """QuerySet that prevents application-level mutation."""

    def update(self, **_kwargs: object) -> int:
        raise RuntimeError("Audit events cannot be updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise RuntimeError("Audit events cannot be deleted.")


class AuditEventManager(models.Manager["AuditEvent"]):
    """Manager returning an append-only queryset."""

    def get_queryset(self) -> AuditEventQuerySet:
        return AuditEventQuerySet(
            model=self.model,
            using=self._db,
        )


class AuditEvent(UUIDModel):
    """Immutable record of a security-relevant action."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    action = models.CharField(
        max_length=120,
        db_index=True,
    )
    resource_type = models.CharField(
        max_length=120,
        db_index=True,
    )
    resource_id = models.CharField(
        max_length=128,
        db_index=True,
    )

    request_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
    )
    source_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )
    user_agent = models.CharField(
        max_length=512,
        blank=True,
    )

    before_state = models.JSONField(
        default=dict,
        blank=True,
    )
    after_state = models.JSONField(
        default=dict,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    occurred_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    objects = AuditEventManager()

    class Meta:
        ordering = ("-occurred_at",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organization", "-occurred_at"),
                name="audit_org_time_idx",
            ),
            models.Index(
                fields=("organization", "action"),
                name="audit_org_action_idx",
            ),
            models.Index(
                fields=("resource_type", "resource_id"),
                name="audit_resource_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.resource_type}:{self.resource_id}"

    def delete(
        self,
        _using: str | None = None,
        _keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        raise RuntimeError("Audit events cannot be deleted.")

    def save(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if not self._state.adding:
            raise RuntimeError("Audit events cannot be updated.")

        super().save(*args, **kwargs)
