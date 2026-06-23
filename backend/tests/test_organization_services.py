"""Tests for organization services."""

from typing import Any

import pytest
from django.core import mail

from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.models import AuditEvent
from agentproof_backend.apps.organizations.exceptions import (
    InvitationEmailMismatch,
    LastOwnerRequired,
    OrganizationPermissionDenied,
)
from agentproof_backend.apps.organizations.models import (
    InvitationRole,
    Membership,
    MembershipRole,
    MembershipStatus,
)
from agentproof_backend.apps.organizations.services import (
    accept_invitation,
    create_invitation,
    remove_membership,
    update_membership,
)
from tests.organization_helpers import (
    add_member,
    create_test_organization,
    create_user,
)

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-three-test",
    source_ip="127.0.0.1",
    user_agent="pytest",
)


def test_create_organization_creates_owner_and_audit_events() -> None:
    owner = create_user(
        email="owner@example.com",
    )

    organization, membership = create_test_organization(
        owner=owner,
    )

    assert membership.organization == organization
    assert membership.user == owner
    assert membership.role == MembershipRole.OWNER
    assert membership.status == MembershipStatus.ACTIVE

    assert AuditEvent.objects.filter(
        organization=organization,
        action="organization.created",
    ).exists()

    assert AuditEvent.objects.filter(
        organization=organization,
        action="membership.created",
    ).exists()


def test_invitation_sends_email_after_commit(
    django_capture_on_commit_callbacks: Any,
) -> None:
    owner = create_user(
        email="owner@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = create_invitation(
            actor=owner,
            organization=organization,
            email="new-member@example.com",
            role=InvitationRole.DEVELOPER,
            audit_context=AUDIT_CONTEXT,
        )

    assert len(mail.outbox) == 1
    assert result.token in mail.outbox[0].body
    assert "new-member@example.com" in mail.outbox[0].to


def test_matching_user_can_accept_invitation() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    invited_user = create_user(
        email="member@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    result = create_invitation(
        actor=owner,
        organization=organization,
        email=invited_user.email,
        role=InvitationRole.DEVELOPER,
        audit_context=AUDIT_CONTEXT,
    )

    membership = accept_invitation(
        actor=invited_user,
        token=result.token,
        audit_context=AUDIT_CONTEXT,
    )

    assert membership.organization == organization
    assert membership.user == invited_user
    assert membership.role == MembershipRole.DEVELOPER
    assert membership.status == MembershipStatus.ACTIVE

    result.invitation.refresh_from_db()
    assert result.invitation.accepted_at is not None


def test_invitation_rejects_another_email() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    invited_user = create_user(
        email="member@example.com",
    )
    wrong_user = create_user(
        email="wrong@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    result = create_invitation(
        actor=owner,
        organization=organization,
        email=invited_user.email,
        role=InvitationRole.VIEWER,
        audit_context=AUDIT_CONTEXT,
    )

    with pytest.raises(InvitationEmailMismatch):
        accept_invitation(
            actor=wrong_user,
            token=result.token,
            audit_context=AUDIT_CONTEXT,
        )


def test_final_owner_cannot_be_demoted() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    organization, owner_membership = create_test_organization(
        owner=owner,
    )

    with pytest.raises(LastOwnerRequired):
        update_membership(
            actor=owner,
            organization=organization,
            membership_id=owner_membership.id,
            role=MembershipRole.DEVELOPER,
            status=None,
            audit_context=AUDIT_CONTEXT,
        )


def test_final_owner_cannot_be_removed() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    organization, owner_membership = create_test_organization(
        owner=owner,
    )

    with pytest.raises(LastOwnerRequired):
        remove_membership(
            actor=owner,
            organization=organization,
            membership_id=owner_membership.id,
            audit_context=AUDIT_CONTEXT,
        )


def test_owner_can_be_demoted_when_another_owner_exists() -> None:
    first_owner = create_user(
        email="owner-one@example.com",
    )
    second_owner = create_user(
        email="owner-two@example.com",
    )

    organization, first_membership = create_test_organization(
        owner=first_owner,
    )

    add_member(
        organization=organization,
        user=second_owner,
        role=MembershipRole.OWNER,
    )

    updated = update_membership(
        actor=second_owner,
        organization=organization,
        membership_id=first_membership.id,
        role=MembershipRole.DEVELOPER,
        status=None,
        audit_context=AUDIT_CONTEXT,
    )

    assert updated.role == MembershipRole.DEVELOPER


def test_administrator_cannot_manage_owner() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    administrator = create_user(
        email="admin@example.com",
    )

    organization, owner_membership = create_test_organization(
        owner=owner,
    )

    add_member(
        organization=organization,
        user=administrator,
        role=MembershipRole.ADMINISTRATOR,
    )

    with pytest.raises(OrganizationPermissionDenied):
        update_membership(
            actor=administrator,
            organization=organization,
            membership_id=owner_membership.id,
            role=MembershipRole.VIEWER,
            status=None,
            audit_context=AUDIT_CONTEXT,
        )


def test_membership_is_unique_per_user_and_organization() -> None:
    owner = create_user(
        email="owner@example.com",
    )
    member = create_user(
        email="member@example.com",
    )
    organization, _membership = create_test_organization(
        owner=owner,
    )

    add_member(
        organization=organization,
        user=member,
    )

    assert (
        Membership.objects.filter(
            organization=organization,
            user=member,
        ).count()
        == 1
    )
