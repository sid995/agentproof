"""AgentProof SDK client."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from agentproof.config import AgentProofConfig
from agentproof.exporters.batching import BatchingExporter
from agentproof.schemas.native import TraceEnvelope
from agentproof.trace import TraceContext
from agentproof.transport.base import SyncTransport


class AgentProofClient:
    """User-facing SDK client for trace capture and export."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        environment: str | None = None,
        timeout_seconds: float | str | None = None,
        batch_size: int | str | None = None,
        flush_interval_seconds: float | str | None = None,
        capture_mode: str | None = None,
        error_mode: str | None = None,
        queue_size: int | str | None = None,
        transport: SyncTransport | None = None,
    ) -> None:
        self.config = AgentProofConfig.from_sources(
            api_key=api_key,
            endpoint=endpoint,
            environment=environment,
            timeout_seconds=timeout_seconds,
            batch_size=batch_size,
            flush_interval_seconds=flush_interval_seconds,
            capture_mode=capture_mode,
            error_mode=error_mode,
            queue_size=queue_size,
        )
        self._exporter = BatchingExporter(config=self.config, transport=transport)

    def trace(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        tags: list[str] | None = None,
        user_identifier: str = "",
        session_identifier: str = "",
    ) -> TraceContext:
        """Create a trace context manager."""

        return TraceContext(
            client=self,
            name=name,
            attributes=attributes,
            tags=tags,
            user_identifier=user_identifier,
            session_identifier=session_identifier,
        )

    def capture(self, trace: TraceEnvelope) -> None:
        """Capture a completed trace for export."""

        self._exporter.enqueue(trace)

    def flush(self) -> None:
        """Flush queued telemetry."""

        self._exporter.flush()

    async def async_flush(self) -> None:
        """Async-compatible flush wrapper."""

        await asyncio.to_thread(self.flush)

    def shutdown(self) -> None:
        """Flush queued telemetry and close resources."""

        self._exporter.shutdown()

    async def async_shutdown(self) -> None:
        """Async-compatible shutdown wrapper."""

        await asyncio.to_thread(self.shutdown)
