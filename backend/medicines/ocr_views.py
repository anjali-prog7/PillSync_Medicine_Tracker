"""OCR upload views.

Replaces the previous mock/random OCR generator with a real OCR pipeline:

    Upload → Validate file → Real OCR (RapidOCR) → Knowledge-base verified
    medicine extraction → Structured fields (only from actual text) →
    Response

Anti-hallucination guarantees:
    - Medicine names are verified against the local knowledge base.
    - Doctor / hospital / disease / date are returned ONLY if present in the
      OCR text; otherwise they are "" (frontend shows "Not Available").
    - Rejected uploads (blank / non-medical images) return status
      "no_medicine" and are never saved as successful OCR history.
    - Confidence is the real OCR word-confidence, never random.
"""

import logging

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .ocr_service import process_upload

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ["image/png", "image/jpeg", "image/jpg", "application/pdf"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _detect_type_from_bytes(data: bytes) -> str:
    """Detect the file type from magic bytes (content, not headers).

    This is the authoritative check: headers can be missing or spoofed,
    but the file signature is derived from the actual bytes.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return ""


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_prescription(request):
    """Process a medicine or prescription image/PDF upload via real OCR."""
    uploaded_file = request.FILES.get("file")
    upload_type = request.data.get("upload_type", "medicine")

    if not uploaded_file:
        return Response(
            {"error": "No file provided. Please upload an image or PDF."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > MAX_FILE_SIZE:
        return Response(
            {"error": "File too large. Maximum size is 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        data = uploaded_file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc)
        return Response(
            {"error": "Failed to read the uploaded file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Authoritative content-type detection from magic bytes.
    content_type = _detect_type_from_bytes(data)
    if content_type not in ALLOWED_TYPES:
        logger.info(
            "OCR upload rejected: unreadable/unsupported file '%s' (%d bytes, header=%s)",
            uploaded_file.name,
            uploaded_file.size,
            uploaded_file.content_type,
        )
        return Response(
            {"error": "Unsupported file type. Allowed: PNG, JPG, JPEG, PDF."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.info(
        "OCR upload: user=%s, file=%s (%d bytes, type=%s, upload_type=%s)",
        request.user.username,
        uploaded_file.name,
        uploaded_file.size,
        content_type,
        upload_type,
    )

    result = process_upload(
        data,
        content_type=content_type,
        upload_type=upload_type,
    )

    # A "no_medicine" rejection is a normal, expected outcome (not a server
    # error). Return HTTP 200 so the frontend renders the message cleanly and
    # does NOT add a fake entry to upload history.
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ocr_health_check(request):
    """Health check for the OCR service."""
    try:
        from .ocr_service import _get_engine

        _get_engine()
        engine_ok = True
    except Exception as exc:
        logger.error("OCR health check: engine failed to load: %s", exc)
        engine_ok = False

    return Response(
        {
            "status": "ok" if engine_ok else "degraded",
            "service": "Prescription OCR Service",
            "engine": "rapidocr-onnxruntime" if engine_ok else "unavailable",
            "mode": "real-ocr",
        },
        status=status.HTTP_200_OK,
    )
