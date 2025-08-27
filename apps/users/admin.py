"""
Admin configuration for users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form for admin."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role", "gender", "phone_number")

    def clean_gender(self):
        """Validate gender for workers."""
        gender = self.cleaned_data.get("gender")
        role = self.cleaned_data.get("role")

        if role == User.Role.WORKER and not gender:
            raise admin.ValidationError("Gender must be specified for workers.")

        return gender


class CustomUserChangeForm(UserChangeForm):
    """Custom user change form for admin."""

    class Meta(UserChangeForm.Meta):
        model = User

    def clean_gender(self):
        """Validate gender for workers."""
        gender = self.cleaned_data.get("gender")
        role = self.cleaned_data.get("role")

        if role == User.Role.WORKER and not gender:
            raise admin.ValidationError("Gender must be specified for workers.")

        return gender


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for User model.

    Provides comprehensive user management with filtering and actions.
    """

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = [
        "username",
        "email",
        "role",
        "gender",
        "phone_number",
        "is_active",
        "date_joined",
        "last_login",
    ]

    list_filter = [
        "role",
        "gender",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
        "last_login",
    ]

    search_fields = ["username", "email", "first_name", "last_name", "phone_number"]

    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "role",
                    "gender",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "email",
                    "role",
                    "gender",
                    "phone_number",
                ),
            },
        ),
    )

    readonly_fields = ["date_joined", "last_login"]

    actions = ["activate_users", "deactivate_users", "make_workers", "make_clients"]

    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) were successfully activated.")

    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) were successfully deactivated.")

    deactivate_users.short_description = "Deactivate selected users"

    def make_workers(self, request, queryset):
        """Convert selected users to workers."""
        # Only convert users who have gender specified
        users_with_gender = queryset.exclude(gender__isnull=True)
        updated = users_with_gender.update(role=User.Role.WORKER)

        if updated < queryset.count():
            self.message_user(
                request,
                f"{updated} user(s) converted to workers. "
                f"{queryset.count() - updated} user(s) skipped (no gender specified).",
            )
        else:
            self.message_user(
                request, f"{updated} user(s) were successfully converted to workers."
            )

    make_workers.short_description = "Convert selected users to workers"

    def make_clients(self, request, queryset):
        """Convert selected users to clients."""
        updated = queryset.update(role=User.Role.CLIENT)
        self.message_user(
            request, f"{updated} user(s) were successfully converted to clients."
        )

    make_clients.short_description = "Convert selected users to clients"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of superusers."""
        if obj and obj.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for non-superusers."""
        if not request.user.is_superuser:
            return self.readonly_fields + ("is_superuser", "is_staff")
        return self.readonly_fields
