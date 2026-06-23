"""Request metadata captured with audit events."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class RequestLike(Protocol):
    """Minimum request interface needed for audit metadata."""

    @property
    def META(self) -> Mapping[str, Any]: ...

    @property
    def headers(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Security relevant metadata associated with an action."""

    request_id: str = ""
    source_ip: str | None = None
    user_agent: str = ""


def audit_context_from_request(request: RequestLike) -> AuditContext:
    """Build an audit context from a Django or DRF request."""
    raw_ip = request.META.get("REMOTE_ADDR")
    source_ip = str(raw_ip) if raw_ip else None

    return AuditContext(
        request_id=str(getattr(request, "request_id", ""))[:128],
        source_ip=source_ip,
        user_agent=request.headers.get("User-Agent", "")[:512],
    )
