"""
User services for business logic operations.
"""

from typing import List

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from loguru import logger

from apps.utils.exceptions import InsufficientPermissionsError

User = get_user_model()


class UserService:
    """Service class for user-related operations."""
    
    @staticmethod
    def create_user(**kwargs) -> User:
        """
        Create a new user with validation.
        
        Args:
            **kwargs: User creation data including username, password, email, role, gender, phone_number
            
        Returns:
            Created user instance
            
        Raises:
            ValidationError: If user data is invalid
        """
        try:
            # Extract password and remove password_confirm
            password = kwargs.pop('password')
            kwargs.pop('password_confirm', None)  # Remove if present
            
            # Extract other fields
            username = kwargs.pop('username')
            email = kwargs.pop('email', '')
            role = kwargs.pop('role', User.Role.CLIENT)
            gender = kwargs.pop('gender', None)
            phone_number = kwargs.pop('phone_number', '')
            
            # Validate password
            validate_password(password)
            
            if role == User.Role.WORKER and not gender:
                raise ValidationError("Gender must be specified for workers.")
            
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    role=role,
                    gender=gender,
                    phone_number=phone_number,
                    **kwargs
                )
                
                logger.info(f"User {user.id} created with role {role}")
                return user
                
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise
    
    @staticmethod
    def get_user_by_id(user_id: int, requesting_user: User) -> User:
        """
        Get user by ID with permission check.
        
        Args:
            user_id: User ID to retrieve
            requesting_user: User making the request
            
        Returns:
            User instance
            
        Raises:
            User.DoesNotExist: If user doesn't exist
            InsufficientPermissionsError: If requesting user cannot view the target user
        """
        try:
            user = User.objects.select_related().only(
                'id', 'username', 'email', 'first_name', 'last_name', 'role', 
                'gender', 'phone_number', 'is_active', 'date_joined'
            ).get(id=user_id)
        except User.DoesNotExist:
            raise User.DoesNotExist("User not found.")
        
        # Check permissions
        if not UserService._can_user_view_user(requesting_user, user):
            raise InsufficientPermissionsError("Cannot view this user.")
        
        return user
    
    @staticmethod
    def get_users_by_role(role: str, requesting_user: User) -> List[User]:
        """
        Get users by role with permission check.
        
        Args:
            role: Role to filter by
            requesting_user: User making the request
            
        Returns:
            List of users with the specified role
        """
        if not requesting_user.is_admin:
            raise InsufficientPermissionsError("Only admins can view users by role.")
        
        return User.objects.filter(role=role).select_related().only(
            'id', 'username', 'first_name', 'last_name', 'role', 
            'gender', 'is_active', 'date_joined'
        ).order_by('username')
    
    @staticmethod
    def get_workers_by_gender(gender: str, requesting_user: User) -> List[User]:
        """
        Get workers by gender specialization.
        
        Args:
            gender: Gender specialization
            requesting_user: User making the request
            
        Returns:
            List of workers with the specified gender
        """
        if not requesting_user.can_view_orders():
            raise InsufficientPermissionsError("Cannot view workers.")
        
        return User.objects.filter(
            role=User.Role.WORKER,
            gender=gender,
            is_active=True
        ).select_related().only(
            'id', 'username', 'first_name', 'last_name', 'role', 
            'gender', 'is_active', 'date_joined'
        ).order_by('username')
    
    @staticmethod
    def update_user(
        user: User,
        requesting_user: User,
        **kwargs
    ) -> User:
        """
        Update user information with permission check.
        
        Args:
            user: User to update
            requesting_user: User making the update
            **kwargs: Fields to update
            
        Returns:
            Updated user instance
            
        Raises:
            InsufficientPermissionsError: If requesting user cannot update the target user
        """
        if not UserService._can_user_update_user(requesting_user, user):
            raise InsufficientPermissionsError("Cannot update this user.")
        
        try:
            with transaction.atomic():
                # Update fields
                for key, value in kwargs.items():
                    if hasattr(user, key) and key != 'id':
                        setattr(user, key, value)
                
                # Validate worker gender requirement
                if user.role == User.Role.WORKER and not user.gender:
                    raise ValidationError("Gender must be specified for workers.")
                
                user.save()
                
                logger.info(f"User {user.id} updated by user {requesting_user.id}")
                return user
                
        except Exception as e:
            logger.error(f"Failed to update user {user.id}: {e}")
            raise
    
    @staticmethod
    def change_user_password(
        user: User,
        requesting_user: User,
        new_password: str
    ) -> bool:
        """
        Change user password with permission check.
        
        Args:
            user: User to change password for
            requesting_user: User making the request
            new_password: New password
            
        Returns:
            True if password changed successfully
            
        Raises:
            InsufficientPermissionsError: If requesting user cannot change the target user's password
        """
        if not UserService._can_user_update_user(requesting_user, user):
            raise InsufficientPermissionsError("Cannot change this user's password.")
        
        try:
            # Validate new password
            validate_password(new_password)
            
            user.set_password(new_password)
            user.save()
            
            logger.info(f"Password changed for user {user.id} by user {requesting_user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to change password for user {user.id}: {e}")
            raise
    
    @staticmethod
    def deactivate_user(
        user: User,
        requesting_user: User,
        reason: str = ""
    ) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user: User to deactivate
            requesting_user: User making the request
            reason: Reason for deactivation
            
        Returns:
            True if user deactivated successfully
            
        Raises:
            InsufficientPermissionsError: If requesting user cannot deactivate the target user
        """
        if not requesting_user.is_admin:
            raise InsufficientPermissionsError("Only admins can deactivate users.")
        
        if user == requesting_user:
            raise InsufficientPermissionsError("Cannot deactivate your own account.")
        
        try:
            user.is_active = False
            user.save()
            
            logger.info(f"User {user.id} deactivated by admin {requesting_user.id}. Reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deactivate user {user.id}: {e}")
            raise
    
    @staticmethod
    def activate_user(
        user: User,
        requesting_user: User
    ) -> bool:
        """
        Activate a user account.
        
        Args:
            user: User to activate
            requesting_user: User making the request
            
        Returns:
            True if user activated successfully
            
        Raises:
            InsufficientPermissionsError: If requesting user cannot activate the target user
        """
        if not requesting_user.is_admin:
            raise InsufficientPermissionsError("Only admins can activate users.")
        
        try:
            user.is_active = True
            user.save()
            
            logger.info(f"User {user.id} activated by admin {requesting_user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to activate user {user.id}: {e}")
            raise
    
    @staticmethod
    def _can_user_view_user(requesting_user: User, target_user: User) -> bool:
        """Check if requesting user can view target user."""
        if requesting_user.is_admin:
            return True
        
        if requesting_user == target_user:
            return True
        
        # Workers can view clients they have orders for
        if requesting_user.is_worker and target_user.is_client:
            return True
        
        return False
    
    @staticmethod
    def _can_user_update_user(requesting_user: User, target_user: User) -> bool:
        """Check if requesting user can update target user."""
        if requesting_user.is_admin:
            return True
        
        if requesting_user == target_user:
            return True
        
        return False
