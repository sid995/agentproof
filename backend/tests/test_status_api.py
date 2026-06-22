"""Tests for the public service status API."""

from django.test import Client


def test_status_api_is_public(client: Client) -> None:
    """The public status endpoint should not require authentication."""
    response = client.get("/api/v1/status/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentproof-backend",
        "version": "0.1.0",
    }


def test_openapi_schema_is_available(client: Client) -> None:
    """The OpenAPI schema endpoint should be available."""
    response = client.get("/api/schema/")

    assert response.status_code == 200
    assert "application/vnd.oai.openapi" in response.headers["Content-Type"]
