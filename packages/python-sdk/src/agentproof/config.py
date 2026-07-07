"""Configuration loading for the AgentProof SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

from agentproof.exceptions import AgentProofConfigError

ErrorMode = Literal["silent", "log", "strict"]
CaptureMode = Literal["metadata_only", "redacted", "full"]

DEFAULT_ENDPOINT = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_BATCH_SIZE = 25
DEFAULT_FLUSH_INTERVAL_SECONDS = 2.0
DEFAULT_QUEUE_SIZE = 1000
INGEST_PATH = "/api/v1/ingest/traces"
MAX_BACKEND_RECORDS = 100


def _optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else None


def _float_value(value: float | str | None, *, name: str, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentProofConfigError(f"{name} must be a number") from exc
    if parsed <= 0:
        raise AgentProofConfigError(f"{name} must be greater than zero")
    return parsed


def _int_value(value: int | str | None, *, name: str, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentProofConfigError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise AgentProofConfigError(f"{name} must be greater than zero")
    return parsed


def _error_mode(value: str | None) -> ErrorMode:
    if value is None:
        return "log"
    if value not in ("silent", "log", "strict"):
        raise AgentProofConfigError("error_mode must be one of: silent, log, strict")
    return cast("ErrorMode", value)


def _capture_mode(value: str | None) -> CaptureMode:
    if value is None:
        return "full"
    if value not in ("metadata_only", "redacted", "full"):
        raise AgentProofConfigError("capture_mode must be one of: metadata_only, redacted, full")
    return cast("CaptureMode", value)


@dataclass(frozen=True, slots=True)
class AgentProofConfig:
    """Resolved AgentProof SDK configuration."""

    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    environment: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    batch_size: int = DEFAULT_BATCH_SIZE
    flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS
    capture_mode: CaptureMode = "full"
    error_mode: ErrorMode = "log"
    queue_size: int = DEFAULT_QUEUE_SIZE

    @classmethod
    def from_sources(
        cls,
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
    ) -> AgentProofConfig:
        """Resolve config from explicit values, environment variables, then defaults."""

        resolved_api_key = api_key or _optional_env("AGENTPROOF_API_KEY")
        if not resolved_api_key:
            raise AgentProofConfigError("api_key is required")

        resolved_endpoint = (endpoint or _optional_env("AGENTPROOF_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
        if not resolved_endpoint.startswith(("http://", "https://")):
            raise AgentProofConfigError("endpoint must start with http:// or https://")

        resolved_timeout = _float_value(
            timeout_seconds or _optional_env("AGENTPROOF_TIMEOUT_SECONDS"),
            name="timeout_seconds",
            default=DEFAULT_TIMEOUT_SECONDS,
        )
        resolved_batch_size = _int_value(
            batch_size or _optional_env("AGENTPROOF_BATCH_SIZE"),
            name="batch_size",
            default=DEFAULT_BATCH_SIZE,
        )
        if resolved_batch_size > MAX_BACKEND_RECORDS:
            raise AgentProofConfigError(f"batch_size must be less than or equal to {MAX_BACKEND_RECORDS}")

        resolved_flush_interval = _float_value(
            flush_interval_seconds or _optional_env("AGENTPROOF_FLUSH_INTERVAL_SECONDS"),
            name="flush_interval_seconds",
            default=DEFAULT_FLUSH_INTERVAL_SECONDS,
        )
        return cls(
            api_key=resolved_api_key,
            endpoint=resolved_endpoint,
            environment=environment or _optional_env("AGENTPROOF_ENVIRONMENT") or "",
            timeout_seconds=resolved_timeout,
            batch_size=resolved_batch_size,
            flush_interval_seconds=resolved_flush_interval,
            capture_mode=_capture_mode(capture_mode or _optional_env("AGENTPROOF_CAPTURE_MODE")),
            error_mode=_error_mode(error_mode or _optional_env("AGENTPROOF_ERROR_MODE")),
            queue_size=_int_value(queue_size, name="queue_size", default=DEFAULT_QUEUE_SIZE),
        )

    @property
    def ingest_url(self) -> str:
        """Return the absolute trace-ingestion URL."""

        return f"{self.endpoint}{INGEST_PATH}"
