from django.urls import path
from drf_yasg.openapi import Info
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny

from conf.settings import API_VERSION, BACKEND_DOMAIN


def get_dynamic_description(domain) -> str:
    """
    Get the API description based on the subdomain.
    """
    host = domain.split(":")[0]
    subdomain = host.split(".")[0]
    if subdomain == "test":
        return "Development API"
    elif subdomain == "api":
        return "Production API"
    else:
        return "Generic API"


schema_view = get_schema_view(
    Info(
        title=get_dynamic_description(BACKEND_DOMAIN),
        default_version=API_VERSION,
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    path("", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
