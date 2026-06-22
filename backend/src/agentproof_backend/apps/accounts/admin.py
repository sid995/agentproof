"""Django admin configuration for accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from agentproof_backend.apps.accounts.forms import (
    UserChangeForm,
    UserCreationForm,
)
from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.common.type_utils import allow_runtime_generic

allow_runtime_generic(DjangoUserAdmin)


@admin.register(User)
class UserAdmin(DjangoUserAdmin[User]):
    """Admin interface for the email-based user model."""

    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = (
        "email",
        "display_name",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
    )
    ordering = ("email",)
    search_fields = (
        "email",
        "display_name",
        "first_name",
        "last_name",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                ),
            },
        ),
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "first_name",
                    "last_name",
                ),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                ),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
