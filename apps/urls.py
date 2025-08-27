from django.urls import include, path

urlpatterns = [
    path("orders", include("orders.urls")),
    path("", include("users.urls")),
]
