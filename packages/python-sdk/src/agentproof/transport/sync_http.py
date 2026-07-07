"""Synchronous HTTP transport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from agentproof.exceptions import AgentProofTransportError


class SyncHTTPTransport:
    """Export telemetry using an `httpx.Client`."""

    def __init__(self) -> None:
        self._client = httpx.Client()

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        """POST JSON to the ingestion API."""

        try:
            response = self._client.post(url, json=payload, headers=dict(headers), timeout=request_timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentProofTransportError(str(exc)) from exc

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()
