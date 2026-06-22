"""Custom user model managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from agentproof_backend.apps.accounts.models import User


class UserManager(BaseUserManager["User"]):
    """Manage users whose primary identifier is an email address"""

    use_in_migrations = True

    def _create_user(
        self,
        email: str,
        password: str | None,
        **extra_fields: Any,
    ) -> User:
        if not email:
            raise ValueError("An email address is required.")

        normalized_email = self.normalize_email(email).strip().lower()

        user = self.model(
            email=normalized_email,
            **extra_fields,
        )
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)

        return user

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Create a normal user."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email=email, password=password, **extra_fields)

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Create an administrative superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("A superuser must have is_staff=True.")

        if not extra_fields.get("is_superuser"):
            raise ValueError("A superuser must have is_superuser=True.")

        return self._create_user(
            email=email,
            password=password,
            **extra_fields,
        )
