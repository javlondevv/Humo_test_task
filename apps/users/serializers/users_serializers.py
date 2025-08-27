"""
User serializers for API responses and validation.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.users.models import User


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users.

    Handles user registration with proper validation.
    """

    password = serializers.CharField(
        write_only=True, min_length=8, help_text="User password (minimum 8 characters)"
    )

    password_confirm = serializers.CharField(
        write_only=True, help_text="Confirm password"
    )

    email = serializers.EmailField(
        required=False, allow_blank=True, help_text="User email address (optional)"
    )

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "password_confirm",
            "email",
            "role",
            "gender",
            "phone_number",
            "first_name",
            "last_name",
        ]
        extra_kwargs = {
            "username": {
                "help_text": "Unique username for the user",
                "validators": [UniqueValidator(queryset=User.objects.all())],
            },
            "role": {
                "help_text": "User role in the system",
                "default": User.Role.CLIENT,
            },
            "gender": {
                "help_text": "User gender (required for workers)",
                "required": False,
            },
            "phone_number": {
                "help_text": "User phone number",
                "required": False,
                "allow_blank": True,
            },
            "first_name": {
                "help_text": "User first name",
                "required": False,
                "allow_blank": True,
            },
            "last_name": {
                "help_text": "User last name",
                "required": False,
                "allow_blank": True,
            },
        }

    def validate(self, attrs):
        """Validate user creation data."""
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords don't match."}
            )

        # Validate password strength
        try:
            validate_password(password)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})

        # Validate worker gender requirement
        role = attrs.get("role", User.Role.CLIENT)
        gender = attrs.get("gender")

        if role == User.Role.WORKER and not gender:
            raise serializers.ValidationError(
                {"gender": "Gender must be specified for workers."}
            )

        return attrs

    def create(self, validated_data):
        """Create a new user."""
        # Remove password_confirm from validated data
        validated_data.pop("password_confirm", None)

        # Create user with hashed password
        user = User.objects.create_user(**validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user information.

    Allows updating user fields while maintaining validation.
    """

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "gender",
            "phone_number",
            "is_active",
        ]
        extra_kwargs = {
            "email": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
            "gender": {"required": False},
            "phone_number": {"required": False},
            "is_active": {"required": False},
        }

    def validate(self, attrs):
        """Validate user update data."""
        user = self.instance
        if not user:
            raise serializers.ValidationError("User instance required for updates.")

        # Validate worker gender requirement
        if user.role == User.Role.WORKER:
            gender = attrs.get("gender", user.gender)
            if not gender:
                raise serializers.ValidationError(
                    {"gender": "Gender must be specified for workers."}
                )

        return attrs


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user serializer for profile views.

    Provides complete user information.
    """

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)

    # Computed fields
    is_client = serializers.ReadOnlyField()
    is_worker = serializers.ReadOnlyField()
    is_admin = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "gender",
            "gender_display",
            "phone_number",
            "is_active",
            "date_joined",
            "is_client",
            "is_worker",
            "is_admin",
        ]
        read_only_fields = [
            "id",
            "username",
            "role",
            "date_joined",
            "is_client",
            "is_worker",
            "is_admin",
        ]


class UserListSerializer(serializers.ModelSerializer):
    """
    Simplified user serializer for list views.

    Provides essential user information without sensitive data.
    """

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "gender",
            "gender_display",
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields


class UserPasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing user password.

    Handles password change with validation.
    """

    current_password = serializers.CharField(
        write_only=True, help_text="Current password"
    )

    new_password = serializers.CharField(
        write_only=True, min_length=8, help_text="New password (minimum 8 characters)"
    )

    new_password_confirm = serializers.CharField(
        write_only=True, help_text="Confirm new password"
    )

    def validate(self, attrs):
        """Validate password change data."""
        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError("User context required.")

        current_password = attrs.get("current_password")
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        # Check current password
        if not user.check_password(current_password):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )

        # Check new password confirmation
        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords don't match."}
            )

        # Validate new password strength
        try:
            validate_password(new_password)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"new_password": e.messages})

        return attrs


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login.

    Handles login credentials.
    """

    username = serializers.CharField(help_text="Username or email")

    password = serializers.CharField(write_only=True, help_text="User password")

    def validate_username(self, value):
        """Validate username field."""
        if not value.strip():
            raise serializers.ValidationError("Username cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        """Validate login credentials and authenticate user."""
        username = attrs.get("username")
        password = attrs.get("password")

        if not username or not password:
            raise serializers.ValidationError(
                "Both username and password are required."
            )

        # Authenticate user
        from django.contrib.auth import authenticate

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid username or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        # Add user to validated data
        attrs["user"] = user
        return attrs


class UserFilterSerializer(serializers.Serializer):
    """
    Serializer for user filtering parameters.

    Used in list views for filtering users.
    """

    role = serializers.ChoiceField(
        choices=User.Role.choices, required=False, help_text="Filter by user role"
    )

    gender = serializers.ChoiceField(
        choices=User.Gender.choices, required=False, help_text="Filter by user gender"
    )

    is_active = serializers.BooleanField(
        required=False, help_text="Filter by active status"
    )

    search = serializers.CharField(
        required=False,
        max_length=100,
        help_text="Search in username, first name, and last name",
    )

    date_from = serializers.DateField(
        required=False, help_text="Filter users joined from this date"
    )

    date_to = serializers.DateField(
        required=False, help_text="Filter users joined until this date"
    )

    def validate(self, attrs):
        """Validate filter parameters."""
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_from": "Start date cannot be after end date."}
            )

        return attrs
