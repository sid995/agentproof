"""Projects application configuration."""

from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Configure projects and deployment environments."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.projects"
    label = "projects"
    verbose_name = "Projects"
