"""Public status API."""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import CharField, Serializer

from agentproof_backend.apps.common.type_utils import allow_runtime_generic

allow_runtime_generic(Serializer)


class StatusResponseSerializer(Serializer[dict[str, str]]):
    """Schema for the service status response."""

    status = CharField()
    service = CharField()
    version = CharField()


@extend_schema(operation_id="get_service_status", responses=StatusResponseSerializer, auth=[])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def status_api(_request: Request) -> Response:
    """Return the public API status"""
    return Response({"status": "ok", "service": "agentproof-backend", "version": "0.1.0"})
