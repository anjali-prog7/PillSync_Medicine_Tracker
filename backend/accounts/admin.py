from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Exposes the custom profile fields (incl. verification) to staff."""

    list_display = ("username", "email", "phone", "role", "is_verified", "is_active")
    list_filter = ("role", "is_verified", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Profile",
            {"fields": ("phone", "role", "gender", "date_of_birth", "is_verified")},
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profile", {"fields": ("phone", "role")}),
    )
