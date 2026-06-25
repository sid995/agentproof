"""Project management API."""

from typing import Never
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from agentproof_backend.apps.audit.context import audit_context_from_request
from agentproof_backend.apps.organizations.api import authenticated_user, current_organization
from agentproof_backend.apps.organizations.permissions import HasActiveOrganization
from agentproof_backend.apps.projects.exceptions import (
    EnvironmentNotFound,
    ProjectError,
    ProjectNotFound,
    ProjectPermissionDenied,
)
from agentproof_backend.apps.projects.permissions import CanManageProjects
from agentproof_backend.apps.projects.selectors import (
    environments_for_project,
    get_environment_for_organization,
    get_project_for_organization,
    projects_for_organization,
)
from agentproof_backend.apps.projects.serializers import (
    EnvironmentCreateSerializer,
    EnvironmentSerializer,
    EnvironmentUpdateSerializer,
    ProjectCreateSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)
from agentproof_backend.apps.projects.services import (
    create_environment,
    create_project,
    update_environment,
    update_project,
)


def raise_project_error(error: ProjectError) -> Never:
    """Convert project domain exceptions into DRF responses."""

    if isinstance(error, ProjectPermissionDenied):
        raise PermissionDenied(detail=str(error), code=error.code) from error

    if isinstance(error, (ProjectNotFound, EnvironmentNotFound)):
        raise NotFound(detail=str(error), code=error.code) from error

    raise ValidationError(detail={"code": error.code, "detail": str(error)}) from error


class ProjectListCreateAPIView(APIView):
    """List or create projects for the active organization"""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(responses=ProjectSerializer(many=True))
    def get(self, request: Request) -> Response:
        projects = projects_for_organization(organization=current_organization(request))
        return Response(ProjectSerializer(projects, many=True).data)

    @extend_schema(request=ProjectCreateSerializer, responses={status.HTTP_201_CREATED: ProjectSerializer})
    def post(self, request: Request) -> Response:
        self.check_permissions(request)

        if not CanManageProjects().has_permission(request, self):
            raise PermissionDenied(CanManageProjects.message)

        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            project = create_project(
                actor=authenticated_user(request),
                organization=current_organization(request),
                name=serializer.validated_data["name"],
                requested_slug=serializer.validated_data.get("slug"),
                description=serializer.validated_data.get("description", ""),
                capture_mode=serializer.validated_data["capture_mode"],
                retention_days=serializer.validated_data["retention_days"],
                audit_context=audit_context_from_request(request),
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectDetailAPIView(APIView):
    """Retrieve or update a project."""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(responses=ProjectSerializer)
    def get(self, request: Request, project_id: UUID | str) -> Response:
        try:
            project = get_project_for_organization(
                organization=current_organization(request),
                project_id=project_id,
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(ProjectSerializer(project).data)

    @extend_schema(request=ProjectUpdateSerializer, responses=ProjectSerializer)
    def patch(self, request: Request, project_id: UUID | str) -> Response:
        if not CanManageProjects().has_permission(request, self):
            raise PermissionDenied(CanManageProjects.message)

        serializer = ProjectUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            project = update_project(
                actor=authenticated_user(request),
                organization=current_organization(request),
                project_id=project_id,
                name=serializer.validated_data.get("name"),
                description=serializer.validated_data.get("description"),
                capture_mode=serializer.validated_data.get("capture_mode"),
                retention_days=serializer.validated_data.get("retention_days"),
                audit_context=audit_context_from_request(request),
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(ProjectSerializer(project).data)


class ProjectEnvironmentListCreateAPIView(APIView):
    """List or create environments under a project."""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(responses=EnvironmentSerializer(many=True))
    def get(self, request: Request, project_id: UUID | str) -> Response:
        try:
            project = get_project_for_organization(
                organization=current_organization(request),
                project_id=project_id,
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(EnvironmentSerializer(environments_for_project(project=project), many=True).data)

    @extend_schema(request=EnvironmentCreateSerializer, responses={status.HTTP_201_CREATED: EnvironmentSerializer})
    def post(self, request: Request, project_id: UUID | str) -> Response:
        if not CanManageProjects().has_permission(request, self):
            raise PermissionDenied(CanManageProjects.message)

        serializer = EnvironmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            environment = create_environment(
                actor=authenticated_user(request),
                organization=current_organization(request),
                project_id=project_id,
                name=serializer.validated_data["name"],
                requested_slug=serializer.validated_data.get("slug"),
                environment_type=serializer.validated_data["environment_type"],
                capture_mode_override=serializer.validated_data.get("capture_mode_override", ""),
                retention_days_override=serializer.validated_data.get("retention_days_override"),
                audit_context=audit_context_from_request(request),
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(EnvironmentSerializer(environment).data, status=status.HTTP_201_CREATED)


class EnvironmentDetailAPIView(APIView):
    """Retrieve or update an environment."""

    permission_classes = (IsAuthenticated, HasActiveOrganization)

    @extend_schema(responses=EnvironmentSerializer)
    def get(self, request: Request, environment_id: UUID | str) -> Response:
        try:
            environment = get_environment_for_organization(
                organization=current_organization(request),
                environment_id=environment_id,
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(EnvironmentSerializer(environment).data)

    @extend_schema(request=EnvironmentUpdateSerializer, responses=EnvironmentSerializer)
    def patch(self, request: Request, environment_id: UUID | str) -> Response:
        if not CanManageProjects().has_permission(request, self):
            raise PermissionDenied(CanManageProjects.message)

        serializer = EnvironmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            environment = update_environment(
                actor=authenticated_user(request),
                organization=current_organization(request),
                environment_id=environment_id,
                name=serializer.validated_data.get("name"),
                environment_type=serializer.validated_data.get("environment_type"),
                capture_mode_override=serializer.validated_data.get("capture_mode_override"),
                retention_days_override=serializer.validated_data.get("retention_days_override"),
                clear_retention_days_override=serializer.validated_data.get("retention_days_override") is None
                and "retention_days_override" in serializer.validated_data,
                audit_context=audit_context_from_request(request),
            )
        except ProjectError as error:
            raise_project_error(error)

        return Response(EnvironmentSerializer(environment).data)
