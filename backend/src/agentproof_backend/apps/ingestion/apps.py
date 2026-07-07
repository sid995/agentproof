"""Ingestion application configuration"""

from django.apps import AppConfig


class IngestionConfig(AppConfig):
    """Configure the trace batch ingestion surface"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.ingestion"
    label = "ingestion"
    verbose_name = "Ingestion"
