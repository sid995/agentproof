"""Organization API serializers."""

from typing import Any

from rest_framework import serializers

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.organizations.models import (
    InvitationRole,
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationInvitation,
)


class UserSummarySerializer(serializers.ModelSerializer[User]):
    """Minimal member user representation."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
        )
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer[Organization]):
    """Organization response representation."""

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrganizationCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Create-organization request."""

    name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )
    slug = serializers.CharField(
        max_length=63,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )


class MembershipSerializer(serializers.ModelSerializer[Membership]):
    """Organization membership representation."""

    user = UserSummarySerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = (
            "id",
            "organization",
            "user",
            "role",
            "status",
            "joined_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MembershipUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """Update a membership role or status."""

    role = serializers.ChoiceField(
        choices=MembershipRole.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=MembershipStatus.choices,
        required=False,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide role, status, or both.")

        return attrs


class InvitationCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Create an organization invitation."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=InvitationRole.choices,
    )


class InvitationSerializer(serializers.ModelSerializer[OrganizationInvitation]):
    """Invitation response representation."""

    invited_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = (
            "id",
            "email",
            "role",
            "invited_by",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "created_at",
        )
        read_only_fields = fields


class InvitationAcceptSerializer(serializers.Serializer[dict[str, Any]]):
    """Accept an invitation using its plaintext token."""

    token = serializers.CharField(
        min_length=20,
        max_length=256,
        trim_whitespace=True,
    )
