"""Transport protocols for AgentProof telemetry export."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class SyncTransport(Protocol):
    """Synchronous telemetry transport."""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        """POST a JSON payload or raise an SDK transport exception."""

    def close(self) -> None:
        """Release transport resources."""


class AsyncTransport(Protocol):
    """Asynchronous telemetry transport."""

    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        """POST a JSON payload or raise an SDK transport exception."""

    async def close(self) -> None:
        """Release transport resources."""
