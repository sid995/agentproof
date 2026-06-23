"""Organization domain exceptions."""


class OrganizationError(Exception):
    """Base organization domain error."""

    code = "organization_error"


class OrganizationConflict(OrganizationError):
    """Raised when an organization conflicts with existing data."""

    code = "organization_conflict"


class OrganizationPermissionDenied(OrganizationError):
    """Raised when a membership lacks the required role."""

    code = "organization_permission_denied"


class MembershipNotFound(OrganizationError):
    """Raised when a requested membership does not exist."""

    code = "membership_not_found"


class LastOwnerRequired(OrganizationError):
    """Raised when an operation would remove the final owner."""

    code = "last_owner_required"


class AlreadyMember(OrganizationError):
    """Raised when an invited user already belongs to the organization."""

    code = "already_member"


class PendingInvitationExists(OrganizationError):
    """Raised when a usable invitation already exists."""

    code = "pending_invitation_exists"


class InvitationNotFound(OrganizationError):
    """Raised when an invitation token or identifier is unknown."""

    code = "invitation_not_found"


class InvitationExpired(OrganizationError):
    """Raised when an invitation has expired."""

    code = "invitation_expired"


class InvitationRevoked(OrganizationError):
    """Raised when an invitation has been revoked."""

    code = "invitation_revoked"


class InvitationAlreadyAccepted(OrganizationError):
    """Raised when an invitation has already been consumed."""

    code = "invitation_already_accepted"


class InvitationEmailMismatch(OrganizationError):
    """Raised when the authenticated user has another email."""

    code = "invitation_email_mismatch"
