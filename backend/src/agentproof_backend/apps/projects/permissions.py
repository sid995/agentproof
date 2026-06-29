"""Project permission helpers."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from agentproof_backend.apps.organizations.models import Membership, MembershipRole

PROJECT_RESOURCE_MANAGER_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMINISTRATOR,
    MembershipRole.DEVELOPER,
}

PROJECT_ADMIN_ROLES = {MembershipRole.OWNER, MembershipRole.ADMINISTRATOR}


class HasMembershipRole(BasePermission):
    required_roles: frozenset[str] = frozenset()
    message = "You do not have permission to perform this action."

    def has_permission(self, request: Request, _view: APIView) -> bool:
        membership = getattr(request, "organization_membership", None)
        return isinstance(membership, Membership) and membership.role in self.required_roles


class CanManageProjectResources(HasMembershipRole):
    required_roles = frozenset(PROJECT_RESOURCE_MANAGER_ROLES)
    message = "Owner, administrator, or developer access is required."


class CanAdministerProjects(HasMembershipRole):
    required_roles = frozenset(PROJECT_ADMIN_ROLES)
    message = "Owner or administrator access is required."
