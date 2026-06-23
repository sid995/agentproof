"""Audit application configuration."""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Configure append-only audit records."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.audit"
    label = "audit"
    verbose_name = "Audit"
