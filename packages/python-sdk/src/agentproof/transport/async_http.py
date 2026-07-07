"""Asynchronous HTTP transport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from agentproof.exceptions import AgentProofTransportError


class AsyncHTTPTransport:
    """Export telemetry using an `httpx.AsyncClient`."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        request_timeout: float,
    ) -> None:
        """POST JSON to the ingestion API."""

        try:
            response = await self._client.post(url, json=payload, headers=dict(headers), timeout=request_timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AgentProofTransportError(str(exc)) from exc

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()
