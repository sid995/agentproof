"""Capture mode redaction helpers for ingested traces"""

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from agentproof_backend.apps.projects.models import CaptureMode
from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalSpanEvent, CanonicalTrace

# Keys whose values are always removed in metadata_only mode
_CONTENT_KEYS = frozenset({"input", "output", "arguments", "result", "content", "tool_arguments", "tool_result"})

# Patterns that indicate a value is a secret and must be masked in redacted/full modes
_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_\-]?key|auth|bearer|credential|private[_\-]?key)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_BEARER_PATTERN = re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_API_KEY_PATTERN = re.compile(r"\b(sk|ap|pk|rk)[-_][A-Za-z0-9]{16,}\b")

_MASK = "[REDACTED]"


def _mask_value(value: Any) -> Any:
    """Recursively mask sensitive values in dict/list/str"""

    if isinstance(value, str):
        value = _EMAIL_PATTERN.sub(_MASK, value)
        value = _BEARER_PATTERN.sub(_MASK, value)
        value = _API_KEY_PATTERN.sub(_MASK, value)
        return value

    if isinstance(value, Mapping):
        return {k: (_MASK if _SECRET_KEY_PATTERN.search(str(k)) else _mask_value(v)) for k, v in value.items()}

    if isinstance(value, list):
        return [_mask_value(item) for item in value]

    return value


def _strip_content(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _mask_value(item) for key, item in value.items() if key not in _CONTENT_KEYS}


def _redact_events(events: tuple[CanonicalSpanEvent, ...], *, metadata_only: bool) -> tuple[CanonicalSpanEvent, ...]:
    return tuple(
        replace(
            event,
            attributes=_strip_content(event.attributes) if metadata_only else _mask_value(dict(event.attributes)),
        )
        for event in events
    )


def _redact_span(span: CanonicalSpan, *, metadata_only: bool) -> CanonicalSpan:
    if metadata_only:
        return replace(
            span,
            attributes=_strip_content(span.attributes),
            input={},
            output={},
            events=_redact_events(span.events, metadata_only=True),
        )

    return replace(
        span,
        attributes=_mask_value(dict(span.attributes)),
        input=_mask_value(dict(span.input)),
        output=_mask_value(dict(span.output)),
        events=_redact_events(span.events, metadata_only=False),
    )


def redact_canonical_trace(trace: CanonicalTrace, capture_mode: str) -> CanonicalTrace:
    """Apply capture policy to a canonical trace, returning a new instance"""

    if capture_mode == CaptureMode.METADATA_ONLY:
        return replace(
            trace,
            input={},
            output={},
            attributes=_strip_content(trace.attributes),
            spans=tuple(_redact_span(span, metadata_only=True) for span in trace.spans),
        )

    return replace(
        trace,
        input=_mask_value(dict(trace.input)),
        output=_mask_value(dict(trace.output)),
        attributes=_mask_value(dict(trace.attributes)),
        spans=tuple(_redact_span(span, metadata_only=False) for span in trace.spans),
    )
