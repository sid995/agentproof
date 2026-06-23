"""Read-only Django admin for audit events."""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from agentproof_backend.apps.audit.models import AuditEvent

if TYPE_CHECKING:
    AuditEventAdminBase = admin.ModelAdmin[AuditEvent]
else:
    AuditEventAdminBase = admin.ModelAdmin


@admin.register(AuditEvent)
class AuditEventAdmin(AuditEventAdminBase):
    """Expose audit events as read-only records."""

    list_display = (
        "occurred_at",
        "organization",
        "actor",
        "action",
        "resource_type",
        "resource_id",
    )
    list_filter = (
        "action",
        "resource_type",
        "occurred_at",
    )
    search_fields = (
        "resource_id",
        "request_id",
        "actor__email",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "organization",
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "request_id",
        "source_ip",
        "user_agent",
        "before_state",
        "after_state",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(
        self,
        _request: HttpRequest,
    ) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: AuditEvent | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: AuditEvent | None = None,
    ) -> bool:
        return False
