"""Project web routes."""

from django.urls import path

from agentproof_backend.apps.projects import web

app_name = "project-web"

urlpatterns = [
    path("", web.project_list, name="project-list"),
    path("<uuid:project_id>/", web.project_detail, name="project-detail"),
    path("environments/<uuid:environment_id>/", web.environment_detail, name="environment-detail"),
]
