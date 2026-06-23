"""Organization API routes."""

from django.urls import path

from agentproof_backend.apps.organizations.api import (
    CurrentOrganizationAPIView,
    InvitationAcceptAPIView,
    OrganizationDetailAPIView,
    OrganizationInvitationListCreateAPIView,
    OrganizationInvitationRevokeAPIView,
    OrganizationListCreateAPIView,
    OrganizationMemberDetailAPIView,
    OrganizationMemberListAPIView,
    OrganizationSwitchAPIView,
)

app_name = "organizations"

urlpatterns = [
    path(
        "organizations/",
        OrganizationListCreateAPIView.as_view(),
        name="organization-list-create",
    ),
    path(
        "organizations/current/",
        CurrentOrganizationAPIView.as_view(),
        name="organization-current",
    ),
    path(
        "organizations/<uuid:organization_id>/",
        OrganizationDetailAPIView.as_view(),
        name="organization-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/switch/",
        OrganizationSwitchAPIView.as_view(),
        name="organization-switch",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        OrganizationMemberListAPIView.as_view(),
        name="organization-member-list",
    ),
    path(
        ("organizations/<uuid:organization_id>/members/<uuid:membership_id>/"),
        OrganizationMemberDetailAPIView.as_view(),
        name="organization-member-detail",
    ),
    path(
        ("organizations/<uuid:organization_id>/invitations/"),
        OrganizationInvitationListCreateAPIView.as_view(),
        name="organization-invitation-list-create",
    ),
    path(
        ("organizations/<uuid:organization_id>/invitations/<uuid:invitation_id>/revoke/"),
        OrganizationInvitationRevokeAPIView.as_view(),
        name="organization-invitation-revoke",
    ),
    path(
        "invitations/accept/",
        InvitationAcceptAPIView.as_view(),
        name="invitation-accept",
    ),
]
