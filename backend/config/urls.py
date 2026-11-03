"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/transactions/", include("transactions.urls")),
    path("api/", include("detection.urls")),  # detections, dashboard/stats, settings
    path("api/", include("alerts.urls")),     # alerts (delivery log)
]
