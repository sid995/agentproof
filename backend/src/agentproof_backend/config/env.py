"""Typed runtime configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOCAL_SECRET = os.getenv("DEFAULT_LOCAL_SECRET", "")


class RuntimeSettings(BaseSettings):
    """Environment configuration shared by Django and background workers."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["local", "test", "production"] = Field(
        default="local",
        validation_alias="AGENTPROOF_ENVIRONMENT",
    )

    django_secret_key: SecretStr = Field(
        default=SecretStr(DEFAULT_LOCAL_SECRET),
        validation_alias="DJANGO_SECRET_KEY",
    )
    django_debug: bool = Field(
        default=False,
        validation_alias="DJANGO_DEBUG",
    )
    django_allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        validation_alias="DJANGO_ALLOWED_HOSTS",
    )
    django_csrf_trusted_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000",
        validation_alias="DJANGO_CSRF_TRUSTED_ORIGINS",
    )
    django_log_level: str = Field(
        default="INFO",
        validation_alias="DJANGO_LOG_LEVEL",
    )

    database_url: str = Field(
        default="postgresql://agentproof:agentproof@localhost:5432/agentproof",  # noqa: #501 # pragma: allowlist secret
        validation_alias="DATABASE_URL",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    object_storage_backend: Literal["filesystem", "s3"] = Field(
        default="filesystem",
        validation_alias="OBJECT_STORAGE_BACKEND",
    )
    aws_access_key_id: SecretStr | None = Field(
        default=None,
        validation_alias="AWS_ACCESS_KEY_ID",
    )
    aws_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )
    aws_storage_bucket_name: str | None = Field(
        default=None,
        validation_alias="AWS_STORAGE_BUCKET_NAME",
    )
    aws_s3_region_name: str | None = Field(
        default=None,
        validation_alias="AWS_S3_REGION_NAME",
    )
    aws_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias="AWS_S3_ENDPOINT_URL",
    )

    sentry_dsn: SecretStr | None = Field(
        default=None,
        validation_alias="SENTRY_DSN",
    )

    @property
    def allowed_hosts(self) -> list[str]:
        """Return normalized Django allowed hosts."""
        return self._split_csv(self.django_allowed_hosts)

    @property
    def csrf_trusted_origins(self) -> list[str]:
        """Return normalized CSRF trusted origins."""
        return self._split_csv(self.django_csrf_trusted_origins)

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_runtime_settings() -> RuntimeSettings:
    """Load and cache runtime settings."""
    return RuntimeSettings()
