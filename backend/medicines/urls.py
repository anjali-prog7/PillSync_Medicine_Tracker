from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import MedicineViewSet, RefillView
from .ocr_views import upload_prescription, ocr_health_check

router = DefaultRouter()
router.register(r"", MedicineViewSet, basename="medicine")

urlpatterns = [
    # Refill endpoint MUST come before the router include — the router's
    # catch-all "<pk>/" pattern would otherwise match "refill/" as a pk
    # value and return 404 instead of reaching RefillView.
    path("refill/", RefillView.as_view(), name="refill"),

    path("", include(router.urls)),

    # OCR Prescription Upload
    path("prescription/upload/", upload_prescription, name="prescription-upload"),
    path("prescription/health/", ocr_health_check, name="ocr-health-check"),
]