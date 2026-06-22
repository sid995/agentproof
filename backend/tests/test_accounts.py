"""Tests for the custom user model."""

import pytest
from django.contrib.auth import get_user_model

from agentproof_backend.apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_configured_user_model_is_agentproof_user() -> None:
    """Django should use the AgentProof custom user model."""
    assert get_user_model() is User


def test_create_user_normalizes_email() -> None:
    """User creation should normalize the email address."""
    user = User.objects.create_user(
        email="  TEST@EXAMPLE.COM ",
        password="correct-horse-battery-staple",  # pragma: allowlist secret
    )

    assert user.email == "test@example.com"
    assert user.check_password("correct-horse-battery-staple")
    assert user.is_staff is False
    assert user.is_superuser is False


def test_create_superuser_sets_required_flags() -> None:
    """Superusers should receive administrative flags."""
    user = User.objects.create_superuser(
        email="admin@example.com",
        password="correct-horse-battery-staple",  # pragma: allowlist secret
    )

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True


def test_user_requires_email() -> None:
    """A user should not be creatable without an email."""
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(
            email="",
            password="correct-horse-battery-staple",  # pragma: allowlist secret
        )
