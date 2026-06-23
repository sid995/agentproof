"""Audit recording services."""

from typing import Any

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.models import AuditEvent
from agentproof_backend.apps.organizations.models import Organization


def record_audit_event(
    *,
    organization: Organization,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: object,
    context: AuditContext,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append a security-relevant audit event."""

    return AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request_id=context.request_id,
        source_ip=context.source_ip,
        user_agent=context.user_agent,
        before_state=before_state or {},
        after_state=after_state or {},
        metadata=metadata or {},
    )
