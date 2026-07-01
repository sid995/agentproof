"""API key routes."""

from django.urls import path

from agentproof_backend.apps.api_keys.api import (
    APIKeyAuthCheckAPIView,
    APIKeyRevokeAPIView,
    EnvironmentAPIKeyListCreateAPIView,
)

app_name = "api_keys"

urlpatterns = [
    path(
        "environments/<uuid:environment_id>/api-keys/",
        EnvironmentAPIKeyListCreateAPIView.as_view(),
        name="environment-api-key-list-create",
    ),
    path("api-keys/<uuid:api_key_id>/revoke/", APIKeyRevokeAPIView.as_view(), name="api-key-revoke"),
    path(
        "environments/<uuid:environment_id>/auth-check/",
        APIKeyAuthCheckAPIView.as_view(),
        name="environment-api-key-auth-check",
    ),
]
