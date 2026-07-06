"""Telemetry application configuration"""

from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    """Configure canonical traces, spans and normalization."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.telemetry"
    label = "telemetry"
    verbose_name = "Telemetry"
