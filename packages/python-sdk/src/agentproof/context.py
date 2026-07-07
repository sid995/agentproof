"""Context variable state for AgentProof instrumentation."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentproof.span import SpanContext
    from agentproof.trace import TraceContext

current_trace: ContextVar[TraceContext | None] = ContextVar("agentproof_current_trace", default=None)
current_span: ContextVar[SpanContext | None] = ContextVar("agentproof_current_span", default=None)
