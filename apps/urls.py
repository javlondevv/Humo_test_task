from django.urls import path, include

urlpatterns = [
    path("orders", include("orders.urls")),
    path("", include("users.urls")),
    ]