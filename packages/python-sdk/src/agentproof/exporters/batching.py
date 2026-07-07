"""Batching exporters for AgentProof telemetry."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from collections.abc import Iterable

from agentproof.config import AgentProofConfig
from agentproof.exceptions import AgentProofQueueFullError, AgentProofTransportError
from agentproof.schemas.native import BatchEnvelope, IngestRecord, TraceEnvelope
from agentproof.transport.base import AsyncTransport, SyncTransport
from agentproof.transport.sync_http import SyncHTTPTransport

logger = logging.getLogger("agentproof")

MAX_SPANS_PER_BACKEND_BATCH = 500


class BatchingExporter:
    """Thread-backed sync exporter with bounded queueing and flush support."""

    def __init__(self, *, config: AgentProofConfig, transport: SyncTransport | None = None) -> None:
        self.config = config
        self.transport = transport or SyncHTTPTransport()
        self._queue: queue.Queue[TraceEnvelope | None] = queue.Queue(maxsize=config.queue_size)
        self._errors: list[BaseException] = []
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="agentproof-exporter", daemon=True)
        self._thread.start()

    def enqueue(self, trace: TraceEnvelope) -> None:
        """Queue one trace for export."""

        if self._closed:
            self._handle_error(AgentProofQueueFullError("exporter is shut down"))
            return

        try:
            self._queue.put_nowait(trace)
        except queue.Full:
            self._handle_error(AgentProofQueueFullError("AgentProof telemetry queue is full"))

    def flush(self) -> None:
        """Block until currently queued telemetry has been exported."""

        self._queue.join()
        if self.config.error_mode == "strict" and self._errors:
            error = self._errors.pop(0)
            if isinstance(error, Exception):
                raise error
            raise AgentProofTransportError(str(error))

    def shutdown(self) -> None:
        """Flush telemetry and stop the background worker."""

        if self._closed:
            return

        self.flush()
        self._closed = True
        self._queue.put(None)
        self._thread.join(timeout=max(self.config.timeout_seconds, 1.0))
        self.transport.close()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            batch: list[TraceEnvelope] = []
            try:
                if item is None:
                    self._queue.task_done()
                    return
                batch.append(item)
                span_count = len(item.spans)
                while len(batch) < self.config.batch_size and span_count < MAX_SPANS_PER_BACKEND_BATCH:
                    try:
                        next_item = self._queue.get(timeout=self.config.flush_interval_seconds)
                    except queue.Empty:
                        break
                    if next_item is None:
                        self._queue.task_done()
                        self._queue.put(None)
                        break
                    next_span_count = len(next_item.spans)
                    if span_count + next_span_count > MAX_SPANS_PER_BACKEND_BATCH:
                        self._queue.task_done()
                        self._queue.put(next_item)
                        break
                    batch.append(next_item)
                    span_count += next_span_count
                self._send_batch(batch)
            finally:
                for _trace in batch:
                    self._queue.task_done()

    def _send_batch(self, traces: Iterable[TraceEnvelope]) -> None:
        records = [IngestRecord(record_id=trace.trace_id, payload=trace) for trace in traces]
        if not records:
            return
        payload = BatchEnvelope(records=records).model_dump(mode="json")
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agentproof-sdk/0.1.0",
        }
        last_error: AgentProofTransportError | None = None
        for attempt in range(3):
            try:
                self.transport.post_json(
                    self.config.ingest_url,
                    headers=headers,
                    payload=payload,
                    request_timeout=self.config.timeout_seconds,
                )
                return
            except AgentProofTransportError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.1 * (2**attempt))
        if last_error is not None:
            self._handle_error(last_error)

    def _handle_error(self, error: BaseException) -> None:
        if self.config.error_mode == "silent":
            return
        if self.config.error_mode == "log":
            logger.warning("agentproof_export_failed", exc_info=error)
            return
        self._errors.append(error)


class AsyncBatchingExporter:
    """Async exporter used by `AgentProofClient.aflush` and async-only integrations."""

    def __init__(self, *, config: AgentProofConfig, transport: AsyncTransport) -> None:
        self.config = config
        self.transport = transport
        self._queue: asyncio.Queue[TraceEnvelope] = asyncio.Queue(maxsize=config.queue_size)

    async def enqueue(self, trace: TraceEnvelope) -> None:
        """Queue one trace asynchronously."""

        try:
            self._queue.put_nowait(trace)
        except asyncio.QueueFull as exc:
            if self.config.error_mode == "strict":
                raise AgentProofQueueFullError("AgentProof telemetry queue is full") from exc
            if self.config.error_mode == "log":
                logger.warning("agentproof_async_queue_full")

    async def flush(self) -> None:
        """Export all queued traces."""

        traces: list[TraceEnvelope] = []
        while not self._queue.empty() and len(traces) < self.config.batch_size:
            traces.append(self._queue.get_nowait())
        if not traces:
            return
        payload = BatchEnvelope(
            records=[IngestRecord(record_id=trace.trace_id, payload=trace) for trace in traces]
        ).model_dump(mode="json")
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agentproof-sdk/0.1.0",
        }
        try:
            await self.transport.post_json(
                self.config.ingest_url,
                headers=headers,
                payload=payload,
                request_timeout=self.config.timeout_seconds,
            )
        except AgentProofTransportError:
            if self.config.error_mode == "strict":
                raise
            if self.config.error_mode == "log":
                logger.warning("agentproof_async_export_failed", exc_info=True)

    async def shutdown(self) -> None:
        """Flush and close async transport resources."""

        await self.flush()
        await self.transport.close()
