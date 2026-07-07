"""SDK trace capture tests."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Mapping
from typing import Any

import pytest

from agentproof import AgentProofClient, trace_agent, trace_model, trace_tool
from agentproof.exceptions import AgentProofConfigError, AgentProofQueueFullError, AgentProofTransportError


class RecordingTransport:
    """Test transport that records sent JSON payloads."""

    def __init__(self, *, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.payloads: list[Mapping[str, Any]] = []
        self.headers: list[Mapping[str, str]] = []
        self.urls: list[str] = []
        self.timeouts: list[float] = []
        self.closed = False

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise AgentProofTransportError("temporary failure")
        self.urls.append(url)
        self.headers.append(headers)
        self.payloads.append(payload)
        self.timeouts.append(request_timeout)

    def close(self) -> None:
        self.closed = True


def make_client(
    transport: RecordingTransport | None = None,
    *,
    error_mode: str = "strict",
    queue_size: int | str | None = None,
) -> AgentProofClient:
    return AgentProofClient(
        api_key="ap_live_test_secret",  # pragma: allowlist secret
        endpoint="http://agentproof.test",
        batch_size=10,
        flush_interval_seconds=0.01,
        error_mode=error_mode,
        queue_size=queue_size,
        transport=transport or RecordingTransport(),
    )


def test_trace_context_exports_native_batch() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    with client.trace("support-agent") as trace:
        trace.set_input({"question": "hello"})
        with trace.span("search-documents", span_type="retrieval") as span:
            span.set_output({"documents": 2})

    client.shutdown()

    assert transport.closed
    assert transport.urls == ["http://agentproof.test/api/v1/ingest/traces"]
    assert transport.headers[0]["Authorization"] == "Bearer ap_live_test_secret"
    assert transport.timeouts == [5.0]
    payload = transport.payloads[0]
    assert payload["source"] == "agentproof"
    assert payload["schema_version"] == "agentproof.v1"
    record = payload["records"][0]
    assert record["record_id"] == record["payload"]["trace_id"]
    assert record["payload"]["name"] == "support-agent"
    assert record["payload"]["input"] == {"question": "hello"}
    assert record["payload"]["spans"][0]["name"] == "search-documents"
    assert record["payload"]["spans"][0]["span_type"] == "retrieval"
    assert record["payload"]["spans"][0]["output"] == {"documents": 2}


def test_nested_spans_preserve_parent_ids() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    with client.trace("agent") as trace, trace.span("parent") as parent, trace.span("child") as child:
        assert child.parent_span_id == parent.span_id

    client.shutdown()

    spans = transport.payloads[0]["records"][0]["payload"]["spans"]
    parent_payload = next(span for span in spans if span["name"] == "parent")
    child_payload = next(span for span in spans if span["name"] == "child")
    assert child_payload["parent_span_id"] == parent_payload["span_id"]


def test_exception_marks_trace_and_span_error() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    def fail() -> None:
        with client.trace("agent") as trace, trace.span("work"):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()

    client.shutdown()
    trace_payload = transport.payloads[0]["records"][0]["payload"]
    assert trace_payload["status"] == "error"
    assert trace_payload["error"]["error_type"] == "RuntimeError"
    assert trace_payload["spans"][0]["status"] == "error"
    assert trace_payload["spans"][0]["error"]["error_type"] == "RuntimeError"


def test_async_task_context_is_isolated() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    async def run_test() -> list[str]:
        async with client.trace("async-agent") as trace:

            async def run_span(name: str) -> str:
                async with trace.span(name) as span:
                    await asyncio.sleep(0)
                    return span.parent_span_id

            return list(await asyncio.gather(run_span("one"), run_span("two")))

    parent_ids = asyncio.run(run_test())

    client.shutdown()

    assert parent_ids == ["", ""]
    spans = transport.payloads[0]["records"][0]["payload"]["spans"]
    assert {span["name"] for span in spans} == {"one", "two"}


def test_decorators_capture_sync_functions() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    @trace_agent(client=client, name="decorated-agent")
    def run_agent(value: int) -> int:
        return run_tool(value) + 1

    @trace_tool(client=client, name="decorated-tool")
    def run_tool(value: int) -> int:
        return value * 2

    assert run_agent(3) == 7
    client.shutdown()

    trace_payload = transport.payloads[0]["records"][0]["payload"]
    assert trace_payload["name"] == "decorated-agent"
    assert {span["span_type"] for span in trace_payload["spans"]} == {"agent", "tool"}


def test_decorators_capture_async_functions() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    async def run_test() -> str:
        @trace_agent(client=client, name="async-agent")
        async def run_agent() -> str:
            return await run_model()

        @trace_model(client=client, name="async-model")
        async def run_model() -> str:
            await asyncio.sleep(0)
            return "ok"

        return await run_agent()

    assert asyncio.run(run_test()) == "ok"
    client.shutdown()

    spans = transport.payloads[0]["records"][0]["payload"]["spans"]
    assert {span["span_type"] for span in spans} == {"agent", "model"}


def test_decorator_rejects_generator_function() -> None:
    def values() -> Any:
        yield 1

    with pytest.raises(AgentProofConfigError, match="generator"):
        trace_agent(values)


def test_strict_backpressure_surfaces_on_flush() -> None:
    client = make_client(RecordingTransport())

    client.shutdown()
    client.capture(client.trace("after-shutdown").to_envelope())

    with pytest.raises(AgentProofQueueFullError):
        client.flush()


def test_export_retries_transient_transport_failure() -> None:
    transport = RecordingTransport(fail_times=2)
    client = make_client(transport)

    with client.trace("agent") as trace, trace.span("work"):
        pass

    client.shutdown()

    assert len(transport.payloads) == 1


def test_repeated_shutdown_is_idempotent() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    with client.trace("agent") as trace, trace.span("work"):
        pass

    client.shutdown()
    client.shutdown()

    assert transport.closed


def test_threaded_spans_export_without_losing_children() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    with client.trace("threaded") as trace:
        threads = [
            threading.Thread(target=lambda name=name: trace.span(name).__enter__().__exit__(None, None, None))
            for name in ("a", "b")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    client.shutdown()
    spans = transport.payloads[0]["records"][0]["payload"]["spans"]
    assert {span["name"] for span in spans} == {"a", "b"}
