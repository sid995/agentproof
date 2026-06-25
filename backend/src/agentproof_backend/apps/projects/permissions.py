"""Project permission helpers."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from agentproof_backend.apps.organizations.models import Membership, MembershipRole


class CanManageProjects(BasePermission):
    """Allow owners, administrators, and developers to manage projects"""

    message = "Owner, administrator, or developer access is required"

    def has_permission(self, request: Request, _view: APIView) -> bool:
        membership = getattr(request, "organization_membership", None)

        return isinstance(membership, Membership) and membership.role in {
            MembershipRole.OWNER,
            MembershipRole.ADMINISTRATOR,
            MembershipRole.DEVELOPER,
        }
