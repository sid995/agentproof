"""Ingestion API views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from agentproof_backend.apps.api_keys.authentication import APIKeyCredentials, EnvironmentAPIKeyAuthentication
from agentproof_backend.apps.ingestion.exceptions import BatchEnvelopeInvalid, BatchLimitExceeded
from agentproof_backend.apps.ingestion.serializers import BatchResultSerializer, IngestTraceBatchSerializer
from agentproof_backend.apps.ingestion.services import ingest_trace_batch

MAX_REQUEST_BYTES = 5 * 1024 * 1024  # 5 MiB


class IngestTraceBatchAPIView(APIView):
    """POST /api/v1/ingest/traces — authenticated trace-batch ingestion."""

    authentication_classes = (EnvironmentAPIKeyAuthentication,)
    permission_classes = (AllowAny,)

    @extend_schema(
        request=IngestTraceBatchSerializer,
        responses={
            202: BatchResultSerializer,
            400: OpenApiResponse(description="Malformed envelope, unsupported source/schema, or batch limit exceeded"),
            401: OpenApiResponse(description="Missing or invalid API key"),
            403: OpenApiResponse(description="Insufficient scope or wrong environment"),
            413: OpenApiResponse(description="Request body too large"),
        },
        summary="Ingest a batch of traces",
        description=(
            "Accepts a batch of trace records. Authenticates via Bearer API key with traces:write scope. "
            "Returns 202 with per-record statuses even when some records fail."
        ),
        tags=["Ingestion"],
    )
    def post(self, request: Request) -> Response:
        if not isinstance(request.auth, APIKeyCredentials):
            raise NotAuthenticated("A valid API key is required.")

        content_length = request.META.get("CONTENT_LENGTH")
        if content_length and int(content_length) > MAX_REQUEST_BYTES:
            return Response(
                {"detail": "Request body exceeds the 5 MiB limit."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        serializer = IngestTraceBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        verified = request.auth.verified

        try:
            result = ingest_trace_batch(
                verified=verified,
                source=serializer.validated_data["source"],
                schema_version=serializer.validated_data["schema_version"],
                records=serializer.validated_data["records"],
            )
        except BatchEnvelopeInvalid as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except BatchLimitExceeded as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        out = BatchResultSerializer(
            {
                "batch_id": result.batch_id,
                "summary": result.summary,
                "accepted": [
                    {
                        "record_id": r.record_id,
                        "external_trace_id": r.external_trace_id,
                        "trace_id": r.trace_id,
                        "status": r.status,
                    }
                    for r in result.accepted
                ],
                "duplicates": [
                    {"record_id": r.record_id, "status": r.status, "reason": r.reason} for r in result.duplicates
                ],
                "invalid": [{"record_id": r.record_id, "status": r.status, "reason": r.reason} for r in result.invalid],
                "rejected": [
                    {"record_id": r.record_id, "status": r.status, "reason": r.reason} for r in result.rejected
                ],
            }
        )
        return Response(out.data, status=status.HTTP_202_ACCEPTED)
