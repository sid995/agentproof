"""Tests for operational health endpoints"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_liveness_endpoint(client: Client) -> None:
    """Liveness should report a healthy process."""
    response = client.get("/health/live/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentproof-backend",
    }


def test_readiness_endpoint(client: Client) -> None:
    """Readiness should verify configured infrastucture"""
    response = client.get("/health/ready/")

    assert response.status_code == 200
