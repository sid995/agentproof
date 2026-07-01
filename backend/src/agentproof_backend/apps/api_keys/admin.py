"""Django admin for API keys."""

from typing import TYPE_CHECKING

from django.contrib import admin

from agentproof_backend.apps.api_keys.models import APIKey

if TYPE_CHECKING:
    APIKeyAdminBase = admin.ModelAdmin[APIKey]
else:
    APIKeyAdminBase = admin.ModelAdmin


@admin.register(APIKey)
class APIKeyAdmin(APIKeyAdminBase):
    """Admin view that keeps secret material read-only and hidden."""

    list_display = ("name", "prefix", "environment", "project", "organization", "expires_at", "revoked_at")
    list_filter = ("organization", "project", "environment", "revoked_at")
    search_fields = ("name", "prefix", "environment__name", "project__name", "organization__name")
    readonly_fields = (
        "id",
        "prefix",
        "key_hash",
        "created_at",
        "updated_at",
        "last_used_at",
        "revoked_at",
    )
