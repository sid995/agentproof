"""Account application configuration."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configure the AgentProof accounts application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agentproof_backend.apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
