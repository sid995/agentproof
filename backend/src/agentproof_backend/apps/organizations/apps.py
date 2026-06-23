"""Organizations application configuration."""

from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    """Configure multi-tenant organization functionality."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.organizations"
    label = "organizations"
    verbose_name = "Organizations"
