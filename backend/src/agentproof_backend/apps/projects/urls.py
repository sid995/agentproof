"""Project API Routes"""

from django.urls import path

from agentproof_backend.apps.projects.api import (
    EnvironmentDetailAPIView,
    ProjectDetailAPIView,
    ProjectEnvironmentListCreateAPIView,
    ProjectListCreateAPIView,
)

app_name = "projects"

urlpatterns = [
    path("projects/", ProjectListCreateAPIView.as_view(), name="project-list-create"),
    path("projects/<uuid:project_id>/", ProjectDetailAPIView.as_view(), name="project-detail"),
    path(
        "projects/<uuid:project_id>/environments/",
        ProjectEnvironmentListCreateAPIView.as_view(),
        name="project-environment-list-create",
    ),
    path(
        "environments/<uuid:environment_id>/",
        EnvironmentDetailAPIView.as_view(),
        name="environment-detail",
    ),
]
