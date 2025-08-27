"""
User views for API endpoints.
"""

import logging

from loguru import logger
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import PermissionDenied

from apps.users.models import User
from apps.users.serializers.users_serializers import (
    UserCreateSerializer,
    UserUpdateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserPasswordChangeSerializer,
    UserLoginSerializer
)
from apps.users.services import UserService
from apps.utils.exceptions import InsufficientPermissionsError



class UserRegisterView(generics.CreateAPIView):
    """
    Register a new user.
    
    Public endpoint for user registration.
    """
    
    serializer_class = UserCreateSerializer
    permission_classes = []
    
    def perform_create(self, serializer):
        """Create user using service layer."""
        try:
            user = UserService.create_user(
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', ''),
                role=serializer.validated_data.get('role', User.Role.CLIENT),
                gender=serializer.validated_data.get('gender'),
                phone_number=serializer.validated_data.get('phone_number', ''),
            )
            
            serializer.instance = user
            
        except InsufficientPermissionsError as e:
            logger.warning(f"User {self.request.user.id} attempted to create user without permission")
            raise PermissionDenied(str(e))
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise


class UserLoginView(generics.GenericAPIView):
    """
    User login/sign-in endpoint.
    
    Authenticates users and returns JWT tokens.
    """
    
    serializer_class = UserLoginSerializer
    permission_classes = []
    
    def post(self, request, *args, **kwargs):
        """Authenticate user and return JWT tokens."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            user = serializer.validated_data['user']
            tokens = serializer.validated_data['tokens']
            
            logger.info(f"User {user.username} logged in successfully")
            
            return Response({
                'detail': 'Login successful.',
                'user': UserDetailSerializer(user).data,
                'tokens': tokens
            })
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Retrieve and update user profile.
    
    Users can only access their own profile.
    """
    
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return the current user."""
        return self.request.user
    
    def get_serializer_class(self):
        """Return appropriate serializer based on HTTP method."""
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserDetailSerializer
    
    def update(self, request, *args, **kwargs):
        """Update user profile."""
        try:
            user = self.get_object()
            
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_user = UserService.update_user(
                user=user,
                requesting_user=request.user,
                **serializer.validated_data
            )
            
            response_serializer = UserDetailSerializer(updated_user)
            return Response(response_serializer.data)
            
        except InsufficientPermissionsError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f"Failed to update user profile: {e}")
            raise


class UserListView(generics.ListAPIView):
    """
    List users based on permissions.
    
    Only admins can view all users, others see limited information.
    """
    
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'gender', 'is_active']
    search_fields = ['username', 'first_name', 'last_name']
    ordering_fields = ['username', 'date_joined', 'first_name', 'last_name']
    ordering = ['username']
    
    def get_queryset(self):
        """Get users based on permissions."""
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        
        if self.request.user.is_admin:
            return User.objects.all()
        else:
            return User.objects.filter(id=self.request.user.id)
    
    def get_serializer_context(self):
        """Add user to serializer context."""
        context = super().get_serializer_context()
        context['requesting_user'] = self.request.user
        return context


class UserDetailView(generics.RetrieveAPIView):
    """
    Retrieve detailed user information.
    
    Users can view their own profile or profiles they have permission to see.
    """
    
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'
    
    def get_queryset(self):
        """Get users based on permissions."""
        # Handle Swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        return User.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve user with permission check."""
        try:
            user = UserService.get_user_by_id(
                user_id=self.kwargs['pk'],
                requesting_user=request.user
            )
            
            serializer = self.get_serializer(user)
            return Response(serializer.data)
            
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )


class UserPasswordChangeView(generics.GenericAPIView):
    """
    Change user password.
    
    Users can change their own password, admins can change any user's password.
    """
    
    serializer_class = UserPasswordChangeSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Change user password."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            target_user = self.get_object()
            
            if request.user.is_admin and target_user != request.user:
                UserService.change_user_password(
                    user=target_user,
                    new_password=serializer.validated_data['new_password']
                )
            else:
                UserService.change_user_password(
                    user=request.user,
                    new_password=serializer.validated_data['new_password']
                )
            
            logger.info(f"Password changed for user {target_user.username}")
            
            return Response({'detail': 'Password changed successfully.'})
            
        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            raise


class UserManagementView(generics.GenericAPIView):
    """
    Admin-only user management actions.
    
    Handles user activation/deactivation and role management.
    """
    
    serializer_class = UserDetailSerializer
    permission_classes = [IsAdminUser]
    
    def post(self, request, *args, **kwargs):
        """Handle user management action."""
        try:
            action = request.data.get('action')
            user_id = request.data.get('user_id')
            reason = request.data.get('reason', '')
            
            if not user_id:
                return Response(
                    {'detail': 'User ID is required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            target_user = User.objects.get(id=user_id)
            
            if action == 'activate':
                success = UserService.activate_user(target_user, request.user)
                if success:
                    return Response({'detail': 'User activated successfully.'})
                else:
                    return Response(
                        {'detail': 'Failed to activate user.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action == 'deactivate':
                success = UserService.deactivate_user(target_user, request.user, reason)
                if success:
                    return Response({'detail': 'User deactivated successfully.'})
                else:
                    return Response(
                        {'detail': 'Failed to deactivate user.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            elif action == 'update_role':
                new_role = request.data.get('role')
                if not new_role or new_role not in dict(User.Role.choices):
                    return Response(
                        {'detail': 'Valid role is required.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                target_user.role = new_role
                
                if new_role == User.Role.WORKER and not target_user.gender:
                    return Response(
                        {'detail': 'Gender must be specified for workers.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                target_user.save()
                logger.info(f"User {target_user.id} role updated to {new_role} by admin {request.user.id}")
                
                return Response({'detail': 'User role updated successfully.'})
            
            else:
                return Response(
                    {'detail': f'Unknown action: {action}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )


class WorkerListView(generics.ListAPIView):
    """
    List workers by gender specialization.
    
    Used for finding available workers for orders.
    """
    
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get workers by gender specialization."""
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        gender = self.request.query_params.get('gender')
        if not gender:
            return User.objects.none()
        
        try:
            return UserService.get_workers_by_gender(gender, self.request.user)
        except InsufficientPermissionsError:
            return User.objects.none()
    
    def list(self, request, *args, **kwargs):
        """List workers with permission check."""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
            
        except InsufficientPermissionsError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
