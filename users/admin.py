from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Django admin configuration for the custom User model.
    """

    model = User

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_owner",
        "is_tenant",
        "is_staff",
        "is_active",
        "is_verified",
    )

    list_filter = (
        "is_owner",
        "is_tenant",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "email",
        "first_name",
        "middle_name",
        "last_name",
    )

    ordering = ("email",)

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
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "dob",
                    "address",
                ),
            },
        ),
        (
            "User Information",
            {
                "fields": (
                    "is_owner",
                    "is_tenant",
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
            "Important Dates",
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
                    "password1",
                    "password2",
                ),
            },
        ),
    )
