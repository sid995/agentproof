"""Organization management API."""

from typing import NoReturn, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import (
    audit_context_from_request,
)
from agentproof_backend.apps.organizations.constants import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
)
from agentproof_backend.apps.organizations.exceptions import (
    InvitationNotFound,
    MembershipNotFound,
    OrganizationError,
    OrganizationPermissionDenied,
)
from agentproof_backend.apps.organizations.models import (
    Membership,
    Organization,
)
from agentproof_backend.apps.organizations.permissions import (
    HasActiveOrganization,
    IsOrganizationAdministrator,
    OrganizationPathMatchesCurrent,
)
from agentproof_backend.apps.organizations.selectors import (
    invitations_for_organization,
    members_for_organization,
    memberships_for_user,
)
from agentproof_backend.apps.organizations.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
)
from agentproof_backend.apps.organizations.services import (
    accept_invitation,
    create_invitation,
    create_organization,
    remove_membership,
    revoke_invitation,
    update_membership,
)


def authenticated_user(request: Request) -> User:
    """Return the authenticated custom user."""
    user = request.user

    if not isinstance(user, User):
        raise PermissionDenied("Authentication is required.")

    return user


def current_organization(request: Request) -> Organization:
    """Return the organization resolved by middleware."""
    organization = getattr(
        request,
        "organization",
        None,
    )

    if not isinstance(organization, Organization):
        raise NotFound("No active organization was selected.")

    return organization


def current_membership(
    request: Request,
) -> Membership:
    """Return the membership resolved by middleware."""
    membership = getattr(
        request,
        "organization_membership",
        None,
    )

    if not isinstance(membership, Membership):
        raise NotFound("No active organization membership was found.")

    return membership


def raise_domain_error(
    error: OrganizationError,
) -> NoReturn:
    """Convert domain exceptions into DRF responses."""
    if isinstance(
        error,
        OrganizationPermissionDenied,
    ):
        raise PermissionDenied(
            detail=str(error),
            code=error.code,
        ) from error

    if isinstance(
        error,
        (
            MembershipNotFound,
            InvitationNotFound,
        ),
    ):
        raise NotFound(
            detail=str(error),
            code=error.code,
        ) from error

    raise ValidationError(
        detail={
            "code": error.code,
            "detail": str(error),
        }
    ) from error


class OrganizationListCreateAPIView(APIView):
    """List memberships or create an organization."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=MembershipSerializer(many=True))
    def get(self, request: Request) -> Response:
        user = authenticated_user(request)

        memberships = memberships_for_user(
            user=user,
        )

        serializer = MembershipSerializer(
            memberships,
            many=True,
        )

        return Response(serializer.data)

    @extend_schema(
        request=OrganizationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: MembershipSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        user = authenticated_user(request)

        serializer = OrganizationCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            organization, membership = create_organization(
                actor=user,
                name=serializer.validated_data["name"],
                requested_slug=serializer.validated_data.get("slug"),
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        request.session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization.id)

        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class CurrentOrganizationAPIView(APIView):
    """Return the selected organization membership."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
    )

    @extend_schema(
        request=None,
        responses=MembershipSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(MembershipSerializer(current_membership(request)).data)


class OrganizationDetailAPIView(APIView):
    """Return the currently selected organization."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
        OrganizationPathMatchesCurrent,
    )

    @extend_schema(
        responses=OrganizationSerializer,
    )
    def get(
        self,
        request: Request,
        organization_id: UUID | str,
    ) -> Response:
        del organization_id

        return Response(OrganizationSerializer(current_organization(request)).data)


class OrganizationSwitchAPIView(APIView):
    """Set an organization as the active session tenant."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses=MembershipSerializer,
    )
    def post(
        self,
        request: Request,
        organization_id: UUID | str,
    ) -> Response:
        user = authenticated_user(request)

        membership = (
            memberships_for_user(
                user=user,
            )
            .filter(
                organization_id=organization_id,
            )
            .first()
        )

        if membership is None:
            raise NotFound("The organization membership does not exist.")

        request.session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(membership.organization_id)

        return Response(MembershipSerializer(membership).data)


class OrganizationMemberListAPIView(APIView):
    """List members in the current organization."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
        OrganizationPathMatchesCurrent,
    )

    @extend_schema(
        responses=MembershipSerializer(many=True),
    )
    def get(
        self,
        request: Request,
        organization_id: UUID | str,
    ) -> Response:
        del organization_id

        members = members_for_organization(
            organization=current_organization(request),
        )

        return Response(
            MembershipSerializer(
                members,
                many=True,
            ).data
        )


class OrganizationMemberDetailAPIView(APIView):
    """Update or remove one membership."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
        OrganizationPathMatchesCurrent,
        IsOrganizationAdministrator,
    )

    @extend_schema(
        request=MembershipUpdateSerializer,
        responses=MembershipSerializer,
    )
    def patch(
        self,
        request: Request,
        organization_id: UUID | str,
        membership_id: UUID | str,
    ) -> Response:
        del organization_id

        serializer = MembershipUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            membership = update_membership(
                actor=authenticated_user(request),
                organization=current_organization(request),
                membership_id=membership_id,
                role=serializer.validated_data.get("role"),
                status=serializer.validated_data.get("status"),
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        return Response(MembershipSerializer(membership).data)

    @extend_schema(
        responses={
            status.HTTP_204_NO_CONTENT: None,
        },
    )
    def delete(
        self,
        request: Request,
        organization_id: UUID | str,
        membership_id: UUID | str,
    ) -> Response:
        del organization_id

        try:
            remove_membership(
                actor=authenticated_user(request),
                organization=current_organization(request),
                membership_id=membership_id,
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationInvitationListCreateAPIView(APIView):
    """List or create organization invitations."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
        OrganizationPathMatchesCurrent,
        IsOrganizationAdministrator,
    )

    @extend_schema(
        responses=InvitationSerializer(many=True),
    )
    def get(
        self,
        request: Request,
        organization_id: UUID | str,
    ) -> Response:
        del organization_id

        invitations = invitations_for_organization(
            organization=current_organization(request),
        )

        return Response(
            InvitationSerializer(
                invitations,
                many=True,
            ).data
        )

    @extend_schema(
        request=InvitationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: InvitationSerializer,
        },
    )
    def post(
        self,
        request: Request,
        organization_id: UUID | str,
    ) -> Response:
        del organization_id

        serializer = InvitationCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            result = create_invitation(
                actor=authenticated_user(request),
                organization=current_organization(request),
                email=serializer.validated_data["email"],
                role=serializer.validated_data["role"],
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        return Response(
            InvitationSerializer(result.invitation).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationInvitationRevokeAPIView(APIView):
    """Revoke an unresolved invitation."""

    permission_classes = (
        IsAuthenticated,
        HasActiveOrganization,
        OrganizationPathMatchesCurrent,
        IsOrganizationAdministrator,
    )

    @extend_schema(
        request=None,
        responses=InvitationSerializer,
    )
    def post(
        self,
        request: Request,
        organization_id: UUID | str,
        invitation_id: UUID | str,
    ) -> Response:
        del organization_id

        try:
            invitation = revoke_invitation(
                actor=authenticated_user(request),
                organization=current_organization(request),
                invitation_id=invitation_id,
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        return Response(InvitationSerializer(invitation).data)


class InvitationAcceptAPIView(APIView):
    """Accept an organization invitation."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=InvitationAcceptSerializer,
        responses=MembershipSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = InvitationAcceptSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            membership = accept_invitation(
                actor=authenticated_user(request),
                token=cast(
                    str,
                    serializer.validated_data["token"],
                ),
                audit_context=audit_context_from_request(request),
            )
        except OrganizationError as error:
            raise_domain_error(error)

        request.session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(membership.organization_id)

        return Response(MembershipSerializer(membership).data)
