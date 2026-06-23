"""Organization test helpers."""

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.organizations.models import (
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
)
from agentproof_backend.apps.organizations.services import (
    create_organization,
)


def create_user(
    *,
    email: str,
) -> User:
    """Create a test user."""
    return User.objects.create_user(
        email=email,
        password="correct-horse-battery-staple",  # pragma: allowlist secret
    )


def create_test_organization(
    *,
    owner: User,
    name: str = "Test Organization",
) -> tuple[Organization, Membership]:
    """Create an organization with one owner."""
    return create_organization(
        actor=owner,
        name=name,
        requested_slug=None,
        audit_context=AuditContext(
            request_id="test-request",
            source_ip="127.0.0.1",
            user_agent="pytest",
        ),
    )


def add_member(
    *,
    organization: Organization,
    user: User,
    role: str = MembershipRole.DEVELOPER,
) -> Membership:
    """Add an active test membership."""
    return Membership.objects.create(
        organization=organization,
        user=user,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
