"""
User models for the application.
"""

from django.contrib.auth.models import AbstractUser
from django.db.models import TextChoices, CharField, BooleanField, DateTimeField
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.utils.constants import USER_ROLES


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    
    Supports different roles (client, worker, admin) and gender specialization
    for workers to match with appropriate clients.
    """

    class Role(TextChoices):
        """User role choices."""
        CLIENT = USER_ROLES['CLIENT'], _('Client')
        WORKER = USER_ROLES['WORKER'], _('Worker')
        ADMIN = USER_ROLES['ADMIN'], _('Admin')

    class Gender(TextChoices):
        """Gender choices for worker specialization."""
        MALE = 'male', _('Male')
        FEMALE = 'female', _('Female')

    username = CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )

    role = CharField(
        _('role'),
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        help_text=_('User role in the system')
    )

    gender = CharField(
        _('gender'),
        max_length=10,
        choices=Gender.choices,
        null=True,
        blank=True,
        help_text=_('Gender specialization for workers')
    )

    phone_number = CharField(
        _('phone number'),
        max_length=15,
        blank=True,
        help_text=_('User phone number')
    )

    is_active = BooleanField(
        _('active'),
        default=True,
        help_text=_('Designates whether this user should be treated as active.')
    )

    date_joined = DateTimeField(
        _('date joined'),
        auto_now_add=True
    )

    class Meta:
        """Meta options for User model."""
        verbose_name = _('user')
        verbose_name_plural = _('users')
        db_table = 'users_user'
        ordering = ['-date_joined']

    def __str__(self):
        """String representation of the user."""
        return f"{self.username} ({self.get_role_display()})"

    def clean(self):
        """Validate model fields."""
        super().clean()

        if self.role == self.Role.WORKER and not self.gender:
            raise ValidationError({
                'gender': _('Gender must be specified for workers.')
            })

    @property
    def is_client(self) -> bool:
        """Check if user is a client."""
        return self.role == self.Role.CLIENT

    @property
    def is_worker(self) -> bool:
        """Check if user is a worker."""
        return self.role == self.Role.WORKER

    @property
    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == self.Role.ADMIN

    def can_view_orders(self) -> bool:
        """Check if user can view orders."""
        return self.is_authenticated and self.role in [self.Role.CLIENT, self.Role.WORKER, self.Role.ADMIN]

    def can_create_orders(self) -> bool:
        """Check if user can create orders."""
        return self.is_authenticated and self.role == self.Role.CLIENT

    def can_manage_orders(self) -> bool:
        """Check if user can manage orders."""
        return self.is_authenticated and self.role in [self.Role.WORKER, self.Role.ADMIN]
