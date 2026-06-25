"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from agentproof_backend.apps.common.api import status_api
from agentproof_backend.apps.common.views import (
    liveness,
    readiness,
)

urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
        name="admin",
    ),
    path(
        "api-auth/",
        include("rest_framework.urls"),
    ),
    path(
        "health/live/",
        liveness,
        name="health-live",
    ),
    path(
        "health/ready/",
        readiness,
        name="health-ready",
    ),
    path(
        "api/v1/status/",
        status_api,
        name="api-status",
    ),
    path(
        "api/v1/",
        include("agentproof_backend.apps.organizations.urls"),
    ),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="api-schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="api-redoc",
    ),
    path(
        "api/v1/",
        include("agentproof_backend.apps.projects.urls"),
    ),
]
