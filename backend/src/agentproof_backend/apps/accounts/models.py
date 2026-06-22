"""Account database models."""

from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models

from agentproof_backend.apps.accounts.managers import UserManager


class User(AbstractUser):
    """AgentProof user identified by a unique email address."""

    username = None  # type: ignore[assignment]

    email = models.EmailField(
        "email address",
        unique=True,
    )
    display_name = models.CharField(
        max_length=150,
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        ordering = ("email",)
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email
