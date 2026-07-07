"""Outbox application configuration."""

from django.apps import AppConfig


class OutboxConfig(AppConfig):
    """Configure transactional outbox models and tasks."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.outbox"
    label = "outbox"
    verbose_name = "Outbox"
