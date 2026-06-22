"""Forms for the custom user model."""

from typing import ClassVar

from django.contrib.auth.forms import (
    UserChangeForm as DjangoUserChangeForm,
)
from django.contrib.auth.forms import (
    UserCreationForm as DjangoUserCreationForm,
)

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.common.type_utils import allow_runtime_generic

allow_runtime_generic(DjangoUserCreationForm)
allow_runtime_generic(DjangoUserChangeForm)


class UserCreationForm(DjangoUserCreationForm[User]):
    """Create users through Django admin."""

    class Meta:
        model: ClassVar[type[User]] = User
        fields: ClassVar[tuple[str, ...]] = (
            "email",
            "display_name",
        )


class UserChangeForm(DjangoUserChangeForm[User]):
    """Update users through Django admin."""

    class Meta:
        model: ClassVar[type[User]] = User
        fields: ClassVar[tuple[str, ...]] = (
            "email",
            "display_name",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )
