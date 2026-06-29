"""Organization and membership database models."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from agentproof_backend.apps.common.models import TimeStampedUUIDModel


class OrganizationStatus(models.TextChoices):
    """Organization lifecycle states."""

    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class MembershipRole(models.TextChoices):
    """Roles available within an organization"""

    OWNER = "owner", "Owner"
    ADMINISTRATOR = "administrator", "Administrator"
    DEVELOPER = "developer", "Developer"
    VIEWER = "viewer", "Viewer"


class MembershipStatus(models.TextChoices):
    """Membership lifecycle states."""

    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class InvitationRole(models.TextChoices):
    """Roles assignable through an invitation."""

    ADMINISTRATOR = "administrator", "Administrator"
    DEVELOPER = "developer", "Developer"
    VIEWER = "viewer", "Viewer"


class Organization(TimeStampedUUIDModel):
    """A tenant representing a company or engineering team."""

    name = models.CharField(
        max_length=150,
    )
    slug = models.SlugField(
        max_length=63,
        unique=True,
        allow_unicode=True,
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationStatus,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_organizations",
    )

    class Meta:
        ordering = ("name",)
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(status__in=OrganizationStatus.values),
                name="org_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Membership(TimeStampedUUIDModel):
    """A user's role and status inside an organization."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole,
        default=MembershipRole.VIEWER,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=MembershipStatus,
        default=MembershipStatus.ACTIVE,
        db_index=True,
    )
    joined_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        ordering = (
            "organization__name",
            "user__email",
        )
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="unique_org_membership",
            ),
            models.CheckConstraint(
                condition=Q(role__in=MembershipRole.values),
                name="membership_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=MembershipStatus.values),
                name="membership_status_valid",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=("organization", "status"),
                name="member_org_status_idx",
            ),
            models.Index(
                fields=("organization", "role"),
                name="member_org_role_idx",
            ),
            models.Index(
                fields=("user", "status"),
                name="member_user_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} in {self.organization.name} as {self.role}"


class OrganizationInvitation(TimeStampedUUIDModel):
    """A single-use invitation to join an organization."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField(
        max_length=254,
        db_index=True,
    )
    role = models.CharField(
        max_length=20,
        choices=InvitationRole,
        default=InvitationRole.VIEWER,
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_organization_invitations",
    )
    expires_at = models.DateTimeField(
        db_index=True,
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=("organization", "email"),
                condition=Q(
                    accepted_at__isnull=True,
                    revoked_at__isnull=True,
                ),
                name="unique_pending_org_invite",
            ),
            models.CheckConstraint(
                condition=Q(role__in=InvitationRole.values),
                name="invitation_role_valid",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=("organization", "email"),
                name="invite_org_email_idx",
            ),
            models.Index(
                fields=("organization", "expires_at"),
                name="invite_org_expiry_idx",
            ),
        ]

    @property
    def is_expired(self) -> bool:
        """Return whether the invitation has expired."""
        return self.expires_at <= timezone.now()

    @property
    def is_pending(self) -> bool:
        """Return whether the invitation remains usable."""
        return self.accepted_at is None and self.revoked_at is None and not self.is_expired

    def __str__(self) -> str:
        return f"{self.email} invited to {self.organization.name}"
