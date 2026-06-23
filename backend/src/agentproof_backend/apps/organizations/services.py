"""State-changing organization use cases."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import UUID

from django.contrib.auth.base_user import BaseUserManager
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.services import record_audit_event
from agentproof_backend.apps.organizations.emails import (
    send_organization_invitation_email,
)
from agentproof_backend.apps.organizations.exceptions import (
    AlreadyMember,
    InvitationAlreadyAccepted,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    LastOwnerRequired,
    MembershipNotFound,
    OrganizationConflict,
    OrganizationError,
    OrganizationPermissionDenied,
    PendingInvitationExists,
)
from agentproof_backend.apps.organizations.models import (
    InvitationRole,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationInvitation,
    OrganizationStatus,
)

MANAGER_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMINISTRATOR,
}


@dataclass(frozen=True, slots=True)
class CreatedInvitation:
    """Invitation result containing the one-time plaintext token."""

    invitation: OrganizationInvitation
    token: str


def normalize_email(email: str) -> str:
    """Normalize an email for membership and invitation comparisons."""
    return BaseUserManager.normalize_email(email).strip().lower()


def hash_invitation_token(token: str) -> str:
    """Hash a plaintext invitation token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def membership_snapshot(
    membership: Membership,
) -> dict[str, Any]:
    """Create a serializable membership audit snapshot."""
    return {
        "id": str(membership.id),
        "organization_id": str(membership.organization_id),
        "user_id": str(membership.user_id),
        "role": membership.role,
        "status": membership.status,
    }


def _build_available_slug(
    *,
    name: str,
    requested_slug: str | None,
) -> str:
    source = requested_slug or name

    base_slug = slugify(
        source,
        allow_unicode=True,
    )[:63].strip("-")

    if not base_slug:
        base_slug = f"organization-{uuid.uuid4().hex[:8]}"

    candidate = base_slug

    while Organization.objects.filter(slug=candidate).exists():
        suffix = uuid.uuid4().hex[:8]
        candidate = f"{base_slug[:54]}-{suffix}"

    return candidate


def _locked_actor_membership(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    try:
        membership = (
            Membership.objects.select_for_update()
            .select_related(
                "organization",
                "user",
            )
            .get(
                organization=organization,
                user=actor,
                status=MembershipStatus.ACTIVE,
            )
        )
    except Membership.DoesNotExist as exc:
        raise OrganizationPermissionDenied("You are not an active organization member.") from exc

    if organization.status != OrganizationStatus.ACTIVE:
        raise OrganizationPermissionDenied("The organization is not active.")

    return membership


def ensure_can_manage_members(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    """Require owner or administrator access."""
    try:
        membership = Membership.objects.get(
            organization=organization,
            user=actor,
            status=MembershipStatus.ACTIVE,
        )
    except Membership.DoesNotExist as exc:
        raise OrganizationPermissionDenied("You are not an active organization member.") from exc

    if membership.role not in MANAGER_ROLES:
        raise OrganizationPermissionDenied("Owner or administrator access is required.")

    return membership


@transaction.atomic
def create_organization(
    *,
    actor: User,
    name: str,
    requested_slug: str | None,
    audit_context: AuditContext,
) -> tuple[Organization, Membership]:
    """Create an organization and its initial owner membership."""
    normalized_name = name.strip()

    if not normalized_name:
        raise OrganizationError("Organization name cannot be empty.")

    slug = _build_available_slug(
        name=normalized_name,
        requested_slug=requested_slug,
    )

    try:
        organization = Organization.objects.create(
            name=normalized_name,
            slug=slug,
            status=OrganizationStatus.ACTIVE,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise OrganizationConflict("An organization with this slug already exists.") from exc

    membership = Membership.objects.create(
        organization=organization,
        user=actor,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="organization.created",
        resource_type="organization",
        resource_id=organization.id,
        context=audit_context,
        after_state={
            "id": str(organization.id),
            "name": organization.name,
            "slug": organization.slug,
            "status": organization.status,
        },
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="membership.created",
        resource_type="membership",
        resource_id=membership.id,
        context=audit_context,
        after_state=membership_snapshot(membership),
    )

    return organization, membership


@transaction.atomic
def create_invitation(
    *,
    actor: User,
    organization: Organization,
    email: str,
    role: str,
    audit_context: AuditContext,
    expires_in: timedelta = timedelta(days=7),
) -> CreatedInvitation:
    """Create and email a single-use organization invitation."""
    actor_membership = _locked_actor_membership(
        actor=actor,
        organization=organization,
    )

    if actor_membership.role not in MANAGER_ROLES:
        raise OrganizationPermissionDenied("Owner or administrator access is required.")

    if role not in InvitationRole.values:
        raise OrganizationError("Invalid invitation role.")

    if actor_membership.role == MembershipRole.ADMINISTRATOR and role == InvitationRole.ADMINISTRATOR:
        raise OrganizationPermissionDenied("Only an owner can invite an administrator.")

    if expires_in <= timedelta(0):
        raise OrganizationError("Invitation expiration must be in the future.")

    normalized_email = normalize_email(email)

    existing_user = User.objects.filter(
        email=normalized_email,
    ).first()

    if (
        existing_user is not None
        and Membership.objects.filter(
            organization=organization,
            user=existing_user,
        ).exists()
    ):
        raise AlreadyMember("This user already has an organization membership.")

    now = timezone.now()

    pending_invitation = (
        OrganizationInvitation.objects.select_for_update()
        .filter(
            organization=organization,
            email=normalized_email,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        .first()
    )

    if pending_invitation is not None:
        if pending_invitation.expires_at > now:
            raise PendingInvitationExists("A pending invitation already exists for this email.")

        pending_invitation.revoked_at = now
        pending_invitation.save(
            update_fields=(
                "revoked_at",
                "updated_at",
            )
        )

    token = secrets.token_urlsafe(32)

    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=normalized_email,
        role=role,
        token_hash=hash_invitation_token(token),
        invited_by=actor,
        expires_at=now + expires_in,
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="invitation.created",
        resource_type="organization_invitation",
        resource_id=invitation.id,
        context=audit_context,
        after_state={
            "id": str(invitation.id),
            "email": invitation.email,
            "role": invitation.role,
            "expires_at": invitation.expires_at.isoformat(),
        },
    )

    transaction.on_commit(
        partial(
            send_organization_invitation_email,
            invitation_id=invitation.id,
            token=token,
        )
    )

    return CreatedInvitation(
        invitation=invitation,
        token=token,
    )


@transaction.atomic
def accept_invitation(
    *,
    actor: User,
    token: str,
    audit_context: AuditContext,
) -> Membership:
    """Accept a single-use organization invitation."""
    token_hash = hash_invitation_token(token)

    try:
        invitation = (
            OrganizationInvitation.objects.select_for_update().select_related("organization").get(token_hash=token_hash)
        )
    except OrganizationInvitation.DoesNotExist as exc:
        raise InvitationNotFound("The invitation token is invalid.") from exc

    if invitation.accepted_at is not None:
        raise InvitationAlreadyAccepted("This invitation has already been accepted.")

    if invitation.revoked_at is not None:
        raise InvitationRevoked("This invitation has been revoked.")

    if invitation.is_expired:
        raise InvitationExpired("This invitation has expired.")

    if invitation.organization.status != OrganizationStatus.ACTIVE:
        raise OrganizationPermissionDenied("The organization is not active.")

    if normalize_email(actor.email) != invitation.email:
        raise InvitationEmailMismatch("Sign in with the email address that received the invitation.")

    membership, created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=actor,
        defaults={
            "role": invitation.role,
            "status": MembershipStatus.ACTIVE,
        },
    )

    if not created and membership.status != MembershipStatus.ACTIVE:
        membership.role = invitation.role
        membership.status = MembershipStatus.ACTIVE
        membership.save(
            update_fields=(
                "role",
                "status",
                "updated_at",
            )
        )

    invitation.accepted_at = timezone.now()
    invitation.save(
        update_fields=(
            "accepted_at",
            "updated_at",
        )
    )

    record_audit_event(
        organization=invitation.organization,
        actor=actor,
        action="invitation.accepted",
        resource_type="organization_invitation",
        resource_id=invitation.id,
        context=audit_context,
        after_state={
            "membership_id": str(membership.id),
            "user_id": str(actor.id),
            "role": membership.role,
        },
    )

    return membership


def _assert_not_removing_final_owner(
    *,
    membership: Membership,
    desired_role: str,
    desired_status: str,
) -> None:
    owner_is_being_removed = (
        membership.role == MembershipRole.OWNER
        and membership.status == MembershipStatus.ACTIVE
        and (desired_role != MembershipRole.OWNER or desired_status != MembershipStatus.ACTIVE)
    )

    if not owner_is_being_removed:
        return

    owner_ids = list(
        Membership.objects.select_for_update()
        .filter(
            organization=membership.organization,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        .values_list(
            "id",
            flat=True,
        )
    )

    if len(owner_ids) <= 1:
        raise LastOwnerRequired("An organization must retain at least one active owner.")


def _assert_actor_can_manage_target(
    *,
    actor_membership: Membership,
    target: Membership,
    desired_role: str,
) -> None:
    if actor_membership.role == MembershipRole.OWNER:
        return

    if actor_membership.role != MembershipRole.ADMINISTRATOR:
        raise OrganizationPermissionDenied("Owner or administrator access is required.")

    protected_roles = {
        MembershipRole.OWNER,
        MembershipRole.ADMINISTRATOR,
    }

    if target.role in protected_roles or desired_role in protected_roles:
        raise OrganizationPermissionDenied("Administrators cannot manage owners or administrators.")


@transaction.atomic
def update_membership(
    *,
    actor: User,
    organization: Organization,
    membership_id: UUID | str,
    role: str | None,
    status: str | None,
    audit_context: AuditContext,
) -> Membership:
    """Update a member role or status with owner protection."""
    actor_membership = _locked_actor_membership(
        actor=actor,
        organization=organization,
    )

    try:
        target = (
            Membership.objects.select_for_update()
            .select_related(
                "organization",
                "user",
            )
            .get(
                id=membership_id,
                organization=organization,
            )
        )
    except Membership.DoesNotExist as exc:
        raise MembershipNotFound("The membership does not exist.") from exc

    desired_role = role if role is not None else target.role
    desired_status = status if status is not None else target.status

    if not isinstance(desired_role, str):
        raise TypeError("desired_role must be a string.")

    if not isinstance(desired_status, str):
        raise TypeError("desired_status must be a string.")

    if desired_role not in MembershipRole.values:
        raise OrganizationError("Invalid membership role.")

    if desired_status not in MembershipStatus.values:
        raise OrganizationError("Invalid membership status.")

    _assert_actor_can_manage_target(
        actor_membership=actor_membership,
        target=target,
        desired_role=desired_role,
    )

    _assert_not_removing_final_owner(
        membership=target,
        desired_role=desired_role,
        desired_status=desired_status,
    )

    before_state = membership_snapshot(target)

    target.role = desired_role
    target.status = desired_status
    target.save(
        update_fields=(
            "role",
            "status",
            "updated_at",
        )
    )

    record_audit_event(
        organization=organization,
        actor=actor,
        action="membership.updated",
        resource_type="membership",
        resource_id=target.id,
        context=audit_context,
        before_state=before_state,
        after_state=membership_snapshot(target),
    )

    return target


@transaction.atomic
def remove_membership(
    *,
    actor: User,
    organization: Organization,
    membership_id: UUID | str,
    audit_context: AuditContext,
) -> None:
    """Remove a membership while preserving the final owner."""
    actor_membership = _locked_actor_membership(
        actor=actor,
        organization=organization,
    )

    try:
        target = (
            Membership.objects.select_for_update()
            .select_related(
                "organization",
                "user",
            )
            .get(
                id=membership_id,
                organization=organization,
            )
        )
    except Membership.DoesNotExist as exc:
        raise MembershipNotFound("The membership does not exist.") from exc

    _assert_actor_can_manage_target(
        actor_membership=actor_membership,
        target=target,
        desired_role=target.role,
    )

    _assert_not_removing_final_owner(
        membership=target,
        desired_role=target.role,
        desired_status=MembershipStatus.SUSPENDED,
    )

    before_state = membership_snapshot(target)
    target_id = target.id

    target.delete()

    record_audit_event(
        organization=organization,
        actor=actor,
        action="membership.removed",
        resource_type="membership",
        resource_id=target_id,
        context=audit_context,
        before_state=before_state,
    )


@transaction.atomic
def revoke_invitation(
    *,
    actor: User,
    organization: Organization,
    invitation_id: UUID | str,
    audit_context: AuditContext,
) -> OrganizationInvitation:
    """Revoke a pending invitation."""
    actor_membership = _locked_actor_membership(
        actor=actor,
        organization=organization,
    )

    if actor_membership.role not in MANAGER_ROLES:
        raise OrganizationPermissionDenied("Owner or administrator access is required.")

    try:
        invitation = OrganizationInvitation.objects.select_for_update().get(
            id=invitation_id,
            organization=organization,
        )
    except OrganizationInvitation.DoesNotExist as exc:
        raise InvitationNotFound("The invitation does not exist.") from exc

    if actor_membership.role == MembershipRole.ADMINISTRATOR and invitation.role == InvitationRole.ADMINISTRATOR:
        raise OrganizationPermissionDenied("Only an owner can revoke an administrator invitation.")

    if invitation.accepted_at is not None:
        raise InvitationAlreadyAccepted("An accepted invitation cannot be revoked.")

    if invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(
            update_fields=(
                "revoked_at",
                "updated_at",
            )
        )

        record_audit_event(
            organization=organization,
            actor=actor,
            action="invitation.revoked",
            resource_type="organization_invitation",
            resource_id=invitation.id,
            context=audit_context,
            before_state={
                "revoked_at": None,
            },
            after_state={
                "revoked_at": invitation.revoked_at.isoformat(),
            },
        )

    return invitation
