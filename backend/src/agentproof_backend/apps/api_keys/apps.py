"""API key application configuration"""

from django.apps import AppConfig


class APIKeysConfig(AppConfig):
    """Configure environment scoped API keys"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.api_keys"
    label = "api_keys"
    verbose_name = "API keys"

    def ready(self) -> None:
        from agentproof_backend.apps.api_keys import schema  # noqa: F401
