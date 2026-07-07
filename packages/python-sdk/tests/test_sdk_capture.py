"""SDK trace capture tests."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable, Mapping
from typing import Any

import pytest

import agentproof.decorators as decorators_module
import agentproof.span as span_module
from agentproof import AgentProofClient, trace_agent, trace_model, trace_tool
from agentproof.exceptions import AgentProofConfigError, AgentProofQueueFullError, AgentProofTransportError
from agentproof.schemas.native import TraceEnvelope
from agentproof.span import SpanContext


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


class BlockingTransport(RecordingTransport):
    """Transport that blocks until released by the test."""

    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        self.started.set()
        self.release.wait(timeout=5)
        super().post_json(url, headers=headers, payload=payload, request_timeout=request_timeout)


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


def test_finished_span_rejects_mutation_helpers() -> None:
    transport = RecordingTransport()
    client = make_client(transport)

    with client.trace("agent") as trace:
        with trace.span("work") as span:
            pass

        mutations = [
            lambda: span.set_input({"value": 1}),
            lambda: span.set_output({"value": 1}),
            lambda: span.set_attributes({"value": 1}),
            lambda: span.set_token_usage(input_tokens=1, output_tokens=2, estimated_cost="0.01"),
            lambda: span.set_model(provider_name="provider", model_name="model"),
            lambda: span.set_tool(tool_name="tool", tool_call_id="call"),
            lambda: span.add_event("event", {"value": 1}),
        ]

        for mutate in mutations:
            with pytest.raises(RuntimeError, match="span has already finished"):
                mutate()

    client.shutdown()


def test_span_elapsed_seconds_returns_monotonic_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    readings = iter([100.0, 102.5])
    monkeypatch.setattr(span_module.time, "monotonic", lambda: next(readings))

    span = SpanContext(trace=object(), name="work")

    assert span.elapsed_seconds() == 2.5


def test_finished_trace_rejects_late_span_attachment() -> None:
    client = make_client(RecordingTransport())
    trace = client.trace("agent")
    trace.finish()

    span = trace.span("late")

    with pytest.raises(RuntimeError, match="trace has already finished"):
        span.finish()

    client.shutdown()


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


def test_decorators_reuse_lazy_default_client(monkeypatch: pytest.MonkeyPatch) -> None:
    created_clients: list[FakeDefaultClient] = []

    class FakeDefaultSpan:
        def __enter__(self) -> FakeDefaultSpan:
            return self

        def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
            return None

    class FakeDefaultTrace:
        def __enter__(self) -> FakeDefaultTrace:
            return self

        def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
            return None

        def span(self, _name: str, *, span_type: str) -> FakeDefaultSpan:
            assert span_type == "agent"
            return FakeDefaultSpan()

    class FakeDefaultClient:
        def __init__(self) -> None:
            created_clients.append(self)

        def trace(self, _name: str) -> FakeDefaultTrace:
            return FakeDefaultTrace()

    monkeypatch.setattr(decorators_module, "_default_client", None)
    monkeypatch.setattr(decorators_module, "AgentProofClient", FakeDefaultClient)

    @decorators_module.trace_agent
    def run_agent() -> str:
        return "ok"

    assert run_agent() == "ok"
    assert run_agent() == "ok"
    assert len(created_clients) == 1


def test_span_decorator_without_active_trace_does_not_create_default_client(monkeypatch: pytest.MonkeyPatch) -> None:
    created_clients: list[object] = []

    class FakeDefaultClient:
        def __init__(self) -> None:
            created_clients.append(self)

    monkeypatch.setattr(decorators_module, "_default_client", None)
    monkeypatch.setattr(decorators_module, "AgentProofClient", FakeDefaultClient)

    @decorators_module.trace_tool
    def run_tool() -> str:
        return "ok"

    assert run_tool() == "ok"
    assert created_clients == []


def test_async_span_decorator_without_active_trace_does_not_create_default_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[object] = []

    class FakeDefaultClient:
        def __init__(self) -> None:
            created_clients.append(self)

    monkeypatch.setattr(decorators_module, "_default_client", None)
    monkeypatch.setattr(decorators_module, "AgentProofClient", FakeDefaultClient)

    @decorators_module.trace_model
    async def run_model() -> str:
        await asyncio.sleep(0)
        return "ok"

    assert asyncio.run(run_model()) == "ok"
    assert created_clients == []


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


def test_shutdown_closes_transport_when_flush_raises() -> None:
    transport = RecordingTransport(fail_times=3)
    client = make_client(transport)

    with client.trace("agent") as trace, trace.span("work"):
        pass

    with pytest.raises(AgentProofTransportError):
        client.shutdown()

    assert transport.closed


def test_enqueue_after_shutdown_starts_is_rejected() -> None:
    transport = BlockingTransport()
    client = make_client(transport)

    with client.trace("agent") as trace, trace.span("work"):
        pass

    shutdown_error: list[BaseException] = []

    def run_shutdown() -> None:
        try:
            client.shutdown()
        except BaseException as exc:
            shutdown_error.append(exc)

    shutdown_thread = threading.Thread(target=run_shutdown)
    shutdown_thread.start()
    assert transport.started.wait(timeout=5)

    client.capture(client.trace("after-shutdown-start").to_envelope())
    transport.release.set()
    shutdown_thread.join(timeout=5)

    assert not shutdown_thread.is_alive()
    assert transport.closed
    assert len(transport.payloads) == 1
    assert len(transport.payloads[0]["records"]) == 1
    assert isinstance(shutdown_error[0], AgentProofQueueFullError)


def test_worker_survives_unexpected_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = RecordingTransport()
    client = make_client(transport)
    exporter = client._exporter
    original_send_batch = exporter._send_batch
    calls = 0

    def flaky_send_batch(traces: Iterable[TraceEnvelope]) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("unexpected exporter failure")
        original_send_batch(traces)

    monkeypatch.setattr(exporter, "_send_batch", flaky_send_batch)

    with client.trace("first") as trace, trace.span("work"):
        pass

    with pytest.raises(RuntimeError, match="unexpected exporter failure"):
        client.flush()

    with client.trace("second") as trace, trace.span("work"):
        pass

    client.shutdown()

    assert [payload["records"][0]["payload"]["name"] for payload in transport.payloads] == ["second"]


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
