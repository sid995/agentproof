"""DRF organization permission classes."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from agentproof_backend.apps.organizations.models import Membership, MembershipRole, Organization


class HasActiveOrganization(BasePermission):
    """Require a resolved active organization membership"""

    message = "Select an active organization first"

    def has_permission(self, request: Request, _view: APIView) -> bool:
        return (
            request.user.is_authenticated and isinstance(getattr(request, "organization", None), Organization)
        ) and isinstance(getattr(request, "organization_membership", None), Membership)


class OrganizationPathMatchesCurrent(BasePermission):
    """Ensure a tenant URL matches the current organization"""

    message = "The requested organization is not active"

    def has_permission(
        self,
        request: Request,
        view: APIView,
    ) -> bool:
        organization = getattr(
            request,
            "organization",
            None,
        )

        organization_id = view.kwargs.get("organization_id")

        return isinstance(organization, Organization) and str(organization.id) == str(organization_id)


class IsOrganizationAdministrator(BasePermission):
    """Require owner or administrator membership."""

    message = "Owner or administrator access is required."

    def has_permission(
        self,
        request: Request,
        _view: APIView,
    ) -> bool:
        membership = getattr(
            request,
            "organization_membership",
            None,
        )

        return isinstance(membership, Membership) and membership.role in {
            MembershipRole.OWNER,
            MembershipRole.ADMINISTRATOR,
        }


class IsOrganizationOwner(BasePermission):
    """Require organization owner membership."""

    message = "Organization owner access is required."

    def has_permission(
        self,
        request: Request,
        _view: APIView,
    ) -> bool:
        membership = getattr(
            request,
            "organization_membership",
            None,
        )

        return isinstance(membership, Membership) and membership.role == MembershipRole.OWNER
