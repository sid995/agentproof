"""Django admin for organizations."""

from typing import TYPE_CHECKING

from django.contrib import admin

from agentproof_backend.apps.organizations.models import (
    Membership,
    Organization,
    OrganizationInvitation,
)

if TYPE_CHECKING:
    MembershipInlineBase = admin.TabularInline[Membership, Organization]
    OrganizationAdminBase = admin.ModelAdmin[Organization]
    MembershipAdminBase = admin.ModelAdmin[Membership]
    OrganizationInvitationAdminBase = admin.ModelAdmin[OrganizationInvitation]
else:
    MembershipInlineBase = admin.TabularInline
    OrganizationAdminBase = admin.ModelAdmin
    MembershipAdminBase = admin.ModelAdmin
    OrganizationInvitationAdminBase = admin.ModelAdmin


class MembershipInline(MembershipInlineBase):
    """Display memberships within an organization."""

    model = Membership
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = (
        "id",
        "joined_at",
        "created_at",
        "updated_at",
    )


@admin.register(Organization)
class OrganizationAdmin(OrganizationAdminBase):
    """Organization administration."""

    list_display = (
        "name",
        "slug",
        "status",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "name",
        "slug",
        "created_by__email",
    )
    autocomplete_fields = ("created_by",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(MembershipAdminBase):
    """Membership administration."""

    list_display = (
        "user",
        "organization",
        "role",
        "status",
        "joined_at",
    )
    list_filter = (
        "role",
        "status",
        "organization",
    )
    search_fields = (
        "user__email",
        "organization__name",
    )
    autocomplete_fields = (
        "user",
        "organization",
    )
    readonly_fields = (
        "id",
        "joined_at",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(OrganizationInvitationAdminBase):
    """Invitation administration."""

    list_display = (
        "email",
        "organization",
        "role",
        "invited_by",
        "expires_at",
        "accepted_at",
        "revoked_at",
    )
    list_filter = (
        "role",
        "organization",
        "created_at",
    )
    search_fields = (
        "email",
        "organization__name",
        "invited_by__email",
    )
    autocomplete_fields = (
        "organization",
        "invited_by",
    )
    readonly_fields = (
        "id",
        "token_hash",
        "accepted_at",
        "revoked_at",
        "created_at",
        "updated_at",
    )
