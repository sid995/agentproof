"""Tests for append-only audit events."""

import pytest

from agentproof_backend.apps.audit.models import AuditEvent
from tests.organization_helpers import (
    create_test_organization,
    create_user,
)

pytestmark = pytest.mark.django_db


def test_audit_events_cannot_be_updated() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    event = AuditEvent.objects.filter(
        organization=organization,
    ).first()

    assert event is not None

    with pytest.raises(
        RuntimeError,
        match="cannot be updated",
    ):
        AuditEvent.objects.filter(
            id=event.id,
        ).update(
            action="tampered",
        )


def test_audit_events_cannot_be_deleted() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    event = AuditEvent.objects.filter(
        organization=organization,
    ).first()

    assert event is not None

    with pytest.raises(
        RuntimeError,
        match="cannot be deleted",
    ):
        event.delete()
