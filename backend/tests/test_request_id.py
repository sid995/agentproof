"""Tests for request correlation identifiers."""

from django.test import Client


def test_response_contains_generated_request_id(client: Client) -> None:
    """responses should contain a generated request identifier."""
    response = client.get("/health/live/")
    request_id = response.headers["X-Request-ID"]

    assert len(request_id) == 32


def test_valid_incoming_request_id_is_preserved(
    client: Client,
) -> None:
    """Valid caller-provided request identifiers should be reused."""
    response = client.get(
        "/health/live/",
        headers={"X-Request-ID": "request-12345678"},
    )

    assert response.headers["X-Request-ID"] == "request-12345678"


def test_invalid_incoming_request_id_is_replaced(
    client: Client,
) -> None:
    """Malformed request identifiers should not be trusted."""
    response = client.get(
        "/health/live/",
        headers={"X-Request-ID": "invalid value with spaces"},
    )

    assert response.headers["X-Request-ID"] != "invalid value with spaces"
    assert len(response.headers["X-Request-ID"]) == 32
