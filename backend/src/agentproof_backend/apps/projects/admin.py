"""Django admin for projects."""

from typing import TYPE_CHECKING

from django.contrib import admin

from agentproof_backend.apps.projects.models import Environment, Project

if TYPE_CHECKING:
    ProjectAdminBase = admin.ModelAdmin[Project]
    EnvironmentAdminBase = admin.ModelAdmin[Environment]
else:
    ProjectAdminBase = admin.ModelAdmin
    EnvironmentAdminBase = admin.ModelAdmin


@admin.register(Project)
class ProjectAdmin(ProjectAdminBase):
    """Admin for tenant projects."""

    list_display = (
        "name",
        "slug",
        "organization",
        "capture_mode",
        "retention_days",
        "created_at",
    )
    list_filter = (
        "capture_mode",
        "organization",
    )
    search_fields = (
        "name",
        "slug",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


@admin.register(Environment)
class EnvironmentAdmin(EnvironmentAdminBase):
    """Admin for project environments."""

    list_display = (
        "name",
        "slug",
        "project",
        "organization",
        "environment_type",
        "capture_mode_override",
        "retention_days_override",
        "created_at",
    )
    list_filter = (
        "environment_type",
        "organization",
        "project",
    )
    search_fields = (
        "name",
        "slug",
        "project__name",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
