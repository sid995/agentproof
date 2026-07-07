"""Function decorators for AgentProof instrumentation."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from agentproof.client import AgentProofClient
from agentproof.context import current_trace
from agentproof.exceptions import AgentProofConfigError

DecoratedFunction = Callable[..., Any]


def _client(client: AgentProofClient | None) -> AgentProofClient:
    return client if client is not None else AgentProofClient()


def _reject_generator(func: Callable[..., Any]) -> None:
    if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
        raise AgentProofConfigError("AgentProof decorators do not support generator functions")


def _already_instrumented(func: Callable[..., Any]) -> bool:
    return bool(getattr(func, "__agentproof_instrumented__", False))


def _mark_instrumented(func: DecoratedFunction) -> DecoratedFunction:
    func.__agentproof_instrumented__ = True  # type: ignore[attr-defined]
    return func


def _decorator(
    *,
    span_type: str,
    client: AgentProofClient | None,
    name: str | None,
    creates_trace: bool,
) -> Callable[[DecoratedFunction], DecoratedFunction]:
    def decorate(func: DecoratedFunction) -> DecoratedFunction:
        _reject_generator(func)
        if _already_instrumented(func):
            return func

        span_name = name or func.__qualname__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                sdk_client = _client(client)
                trace = current_trace.get()
                if trace is None and creates_trace:
                    async with sdk_client.trace(span_name) as new_trace, new_trace.span(span_name, span_type=span_type):
                        return await func(*args, **kwargs)
                if trace is None:
                    async with sdk_client.trace(span_name) as new_trace, new_trace.span(span_name, span_type=span_type):
                        return await func(*args, **kwargs)
                async with trace.span(span_name, span_type=span_type):
                    return await func(*args, **kwargs)

            return _mark_instrumented(async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            sdk_client = _client(client)
            trace = current_trace.get()
            if trace is None and creates_trace:
                with sdk_client.trace(span_name) as new_trace, new_trace.span(span_name, span_type=span_type):
                    return func(*args, **kwargs)
            if trace is None:
                with sdk_client.trace(span_name) as new_trace, new_trace.span(span_name, span_type=span_type):
                    return func(*args, **kwargs)
            with trace.span(span_name, span_type=span_type):
                return func(*args, **kwargs)

        return _mark_instrumented(sync_wrapper)

    return decorate


def trace_agent(
    func: DecoratedFunction | None = None,
    *,
    client: AgentProofClient | None = None,
    name: str | None = None,
) -> DecoratedFunction | Callable[[DecoratedFunction], DecoratedFunction]:
    """Instrument a function as an agent span, creating a trace when needed."""

    decorator = _decorator(span_type="agent", client=client, name=name, creates_trace=True)
    return decorator(func) if func is not None else decorator


def trace_model(
    func: DecoratedFunction | None = None,
    *,
    client: AgentProofClient | None = None,
    name: str | None = None,
) -> DecoratedFunction | Callable[[DecoratedFunction], DecoratedFunction]:
    """Instrument a function as a model span."""

    decorator = _decorator(span_type="model", client=client, name=name, creates_trace=False)
    return decorator(func) if func is not None else decorator


def trace_tool(
    func: DecoratedFunction | None = None,
    *,
    client: AgentProofClient | None = None,
    name: str | None = None,
) -> DecoratedFunction | Callable[[DecoratedFunction], DecoratedFunction]:
    """Instrument a function as a tool span."""

    decorator = _decorator(span_type="tool", client=client, name=name, creates_trace=False)
    return decorator(func) if func is not None else decorator


def trace_retrieval(
    func: DecoratedFunction | None = None,
    *,
    client: AgentProofClient | None = None,
    name: str | None = None,
) -> DecoratedFunction | Callable[[DecoratedFunction], DecoratedFunction]:
    """Instrument a function as a retrieval span."""

    decorator = _decorator(span_type="retrieval", client=client, name=name, creates_trace=False)
    return decorator(func) if func is not None else decorator
