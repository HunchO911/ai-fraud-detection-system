from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DetectionViewSet, SettingsView, StatsView

router = SimpleRouter()
router.register("detections", DetectionViewSet, basename="detection")

urlpatterns = router.urls + [
    path("dashboard/stats/", StatsView.as_view(), name="dashboard-stats"),
    path("settings/", SettingsView.as_view(), name="detection-settings"),
]
