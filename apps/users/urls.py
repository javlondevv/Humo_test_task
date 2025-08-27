"""
URL configuration for users app.
"""

from django.urls import path

from apps.users.views.users_views import (UserDetailView, UserListView,
                                          UserLoginView, UserManagementView,
                                          UserPasswordChangeView,
                                          UserProfileView, UserRegisterView,
                                          WorkerListView)

app_name = "users"

urlpatterns = [
    # User authentication and registration
    path("register/", UserRegisterView.as_view(), name="user-register"),
    path("login/", UserLoginView.as_view(), name="user-login"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    # User management
    path("", UserListView.as_view(), name="user-list"),
    path("<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path(
        "password/change/",
        UserPasswordChangeView.as_view(),
        name="user-password-change",
    ),
    path("management/", UserManagementView.as_view(), name="user-management"),
    # Worker-specific endpoints
    path("workers/", WorkerListView.as_view(), name="worker-list"),
]
