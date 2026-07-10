"""Dataset app configuration."""

from django.apps import AppConfig


class DatasetsConfig(AppConfig):
    """Configure versioned datasets."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.datasets"
    verbose_name = "Datasets"
