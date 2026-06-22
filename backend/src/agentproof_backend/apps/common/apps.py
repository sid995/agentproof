from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Configure common cross cutting functionality."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.common"
    label = "common"
    verbose_name = "Common"
