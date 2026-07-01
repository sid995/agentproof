"""API key management and authentication check endpoints"""

from typing import NoReturn
from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from agentproof_backend.apps.api_keys.authentication import APIKeyCredentials, EnvironmentAPIKeyAuthentication
from agentproof_backend.apps.api_keys.exceptions import APIKeyError, APIKeyNotFound, APIKeyPermissionDenied
from agentproof_backend.apps.api_keys.selectors import api_keys_for_environment
from agentproof_backend.apps.api_keys.serializers import (
    APIKeyAuthCheckSerializer,
    APIKeyCreateSerializer,
    APIKeyCreationResponseSerializer,
    APIKeySerializer,
)
from agentproof_backend.apps.api_keys.services import create_api_key, revoke_api_key
from agentproof_backend.apps.api_keys.throttles import APIKeyRateThrottle
from agentproof_backend.apps.audit.context import audit_context_from_request
from agentproof_backend.apps.organizations.api import authenticated_user, current_organization
from agentproof_backend.apps.organizations.permissions import HasActiveOrganization
from agentproof_backend.apps.projects.exceptions import ProjectError
from agentproof_backend.apps.projects.permissions import CanManageProjectResources
from agentproof_backend.apps.projects.selectors import get_environment_for_organization


def raise_api_key_error(error: APIKeyError) -> NoReturn:
    if isinstance(error, APIKeyPermissionDenied):
        raise PermissionDenied(detail=str(error), code=error.code) from error

    if isinstance(error, APIKeyNotFound):
        raise NotFound(detail=str(error), code=error.code) from error

    raise ValidationError(detail={"code": error.code, "detail": str(error)}) from error


class EnvironmentAPIKeyListCreateAPIView(APIView):
    """List or create API keys for an environment."""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(responses=APIKeySerializer(many=True))
    def get(self, request: Request, environment_id: UUID | str) -> Response:
        organization = current_organization(request)

        try:
            environment = get_environment_for_organization(
                organization=organization,
                environment_id=environment_id,
            )
        except ProjectError as error:
            raise NotFound(str(error)) from error

        keys = api_keys_for_environment(
            organization=organization,
            environment=environment,
        )

        return Response(APIKeySerializer(keys, many=True).data)

    @extend_schema(
        request=APIKeyCreateSerializer,
        responses={status.HTTP_201_CREATED: APIKeyCreationResponseSerializer},
    )
    def post(self, request: Request, environment_id: UUID | str) -> Response:
        if not CanManageProjectResources().has_permission(request, self):
            raise PermissionDenied(CanManageProjectResources.message)

        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization = current_organization(request)

        try:
            environment = get_environment_for_organization(
                organization=organization,
                environment_id=environment_id,
            )
            result = create_api_key(
                actor=authenticated_user(request),
                environment=environment,
                name=serializer.validated_data["name"],
                scopes=serializer.validated_data["scopes"],
                expires_at=serializer.validated_data["expires_at"],
                audit_context=audit_context_from_request(request),
            )
        except (APIKeyError, ProjectError) as error:
            if isinstance(error, APIKeyError):
                raise_api_key_error(error)

            raise NotFound(str(error)) from error

        return Response(
            APIKeyCreationResponseSerializer(result).data,
            status=status.HTTP_201_CREATED,
        )


class APIKeyRevokeAPIView(APIView):
    """Revoke an API key."""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(request=None, responses={status.HTTP_200_OK: OpenApiResponse(response=APIKeySerializer)})
    def post(self, request: Request, api_key_id: UUID | str) -> Response:
        if not CanManageProjectResources().has_permission(request, self):
            raise PermissionDenied(CanManageProjectResources.message)

        try:
            api_key = revoke_api_key(
                actor=authenticated_user(request),
                organization=current_organization(request),
                api_key_id=api_key_id,
                audit_context=audit_context_from_request(request),
            )
        except APIKeyError as error:
            raise_api_key_error(error)

        return Response(APIKeySerializer(api_key).data)


class APIKeyAuthCheckAPIView(APIView):
    """Minimal protected endpoint proving API-key auth works."""

    authentication_classes = (EnvironmentAPIKeyAuthentication,)
    permission_classes = (AllowAny,)
    throttle_classes = (APIKeyRateThrottle,)

    @extend_schema(request=None, responses={status.HTTP_200_OK: OpenApiResponse(APIKeyAuthCheckSerializer)})
    def post(self, request: Request, environment_id: UUID | str) -> Response:
        auth = request.auth

        if not isinstance(auth, APIKeyCredentials):
            raise PermissionDenied("A valid API key is required.")

        verified = auth.verified

        if str(verified.environment_id) != str(environment_id):
            raise PermissionDenied("API key is not valid for this environment.")

        return Response(
            {
                "status": "ok",
                "organization_id": verified.organization_id,
                "project_id": verified.project_id,
                "environment_id": verified.environment_id,
                "scopes": sorted(verified.scopes),
            }
        )
