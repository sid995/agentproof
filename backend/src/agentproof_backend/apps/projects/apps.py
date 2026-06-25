"""Projects application configuration"""

from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Configure project and environment hierarchy"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.projects"
    label = "projects"
