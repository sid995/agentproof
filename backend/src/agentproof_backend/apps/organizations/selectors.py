"""Read-focused organization queries"""

from django.db.models import QuerySet

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.organizations.models import (
    Membership,
    MembershipStatus,
    Organization,
    OrganizationInvitation,
    OrganizationStatus,
)


def memberships_for_user(*, user: User) -> QuerySet[Membership]:
    """Return active memberships visible to a user."""

    return (
        Membership.objects.filter(
            user=user, status=MembershipStatus.ACTIVE, organization__status=OrganizationStatus.ACTIVE
        )
        .select_related(
            "organization",
            "user",
        )
        .order_by(
            "organization__name",
        )
    )


def organizations_for_user(
    *,
    user: User,
) -> QuerySet[Organization]:
    """Return organizations for which a user is an active member."""
    return (
        Organization.objects.filter(
            status=OrganizationStatus.ACTIVE,
            memberships__user=user,
            memberships__status=MembershipStatus.ACTIVE,
        )
        .distinct()
        .order_by("name")
    )


def members_for_organization(
    *,
    organization: Organization,
) -> QuerySet[Membership]:
    """Return memberships for one tenant."""
    return (
        Membership.objects.filter(
            organization=organization,
        )
        .select_related("user")
        .order_by(
            "role",
            "user__email",
        )
    )


def invitations_for_organization(
    *,
    organization: Organization,
) -> QuerySet[OrganizationInvitation]:
    """Return invitations belonging to one tenant."""
    return (
        OrganizationInvitation.objects.filter(
            organization=organization,
        )
        .select_related(
            "organization",
            "invited_by",
        )
        .order_by("-created_at")
    )
