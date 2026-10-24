"""Primary AI engine: Google Gemini Vision extraction.

This module is the FIRST image-understanding step of the pipeline. It
understands printed, handwritten, mixed, low-quality, rotated and blurry
images and returns strictly-typed JSON via Google Structured Output.

Public API:

    * ``extract_prescription(data, content_type)`` -> raw payload | None
    * ``extract_medicine(data, content_type)``      -> raw payload | None

Design guarantees:

    1. Never crashes. Every external call is wrapped; any failure returns
       None so the caller falls back to the OCR pipeline.
    2. Strict schema JSON. The model replies with JSON matching
       ``responseSchema`` (``responseMimeType: application/json``). A
       defensive parser still tolerates markdown fences.
    3. No hallucinated fields. The prompt instructs the model to return
       ``null`` for any field that is not visible/legible. The mappers keep
       that null / empty so the frontend renders "Not Available".
    4. Confidence is returned per medicine AND overall (0-100), so the
       pipeline can decide whether to trust the AI result directly
       (>= 85%) or merge it with OCR (< 85%).
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import threading

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .. import medicine_kb as kb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client (module-level singleton - never recreated per request)
# ---------------------------------------------------------------------------

_session = None
_session_lock = threading.Lock()


def _get_session():
    """Return the shared HTTP session (created once, thread-safe)."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import requests

                _session = requests.Session()
    return _session


def _get_settings():
    from django.conf import settings

    return settings


def _is_enabled() -> bool:
    """True when the Gemini Vision path may be attempted."""
    settings = _get_settings()
    if not getattr(settings, "GEMINI_VISION_EXTRACTION_ENABLED", False):
        return False
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    return bool(api_key)


def _model_name() -> str:
    return getattr(_get_settings(), "GEMINI_VISION_MODEL", "gemini-flash-latest")


def _timeout() -> int:
    return int(getattr(_get_settings(), "GEMINI_VISION_TIMEOUT", 45))


def _max_pages() -> int:
    return int(getattr(_get_settings(), "GEMINI_VISION_MAX_PAGES", 3))


# ---------------------------------------------------------------------------
# Google Structured Output schemas (schema JSON, not free text)
# ---------------------------------------------------------------------------
# Conventions: "If a field is not visible, return null." The mappers below
# convert null/absent to "" so the frontend renders "Not Available".

STRING = {"type": "STRING"}

_MEDICINE_FIELDS = {
    "name": STRING,
    "brand": STRING,
    "generic_name": STRING,
    "strength": STRING,
    "unit": STRING,
    "dosage": STRING,
    "frequency": STRING,
    "timing": STRING,
    "duration": STRING,
    "quantity": STRING,
    "route": STRING,
    "special_instructions": STRING,
    "confidence": {"type": "NUMBER"},
}

MEDICINE_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": dict(_MEDICINE_FIELDS),
    "required": ["name"],
}

PRESCRIPTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "patient": {
            "type": "OBJECT",
            "properties": {
                "name": STRING,
                "age": STRING,
                "gender": STRING,
            },
            "required": ["name", "age", "gender"],
        },
        "doctor": {
            "type": "OBJECT",
            "properties": {
                "name": STRING,
                "registration_number": STRING,
                "hospital": STRING,
                "department": STRING,
            },
            "required": ["name", "registration_number", "hospital", "department"],
        },
        "prescription_date": STRING,
        "disease": STRING,
        "diagnosis": STRING,
        "symptoms": STRING,
        "doctor_notes": STRING,
        "medicines": {
            "type": "ARRAY",
            "items": MEDICINE_ITEM_SCHEMA,
        },
        "confidence": {"type": "NUMBER"},
    },
    "required": ["medicines", "confidence"],
}

MEDICINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": STRING,
        "brand": STRING,
        "generic_name": STRING,
        "strength": STRING,
        "unit": STRING,
        "medicine_type": STRING,
        "manufacturer": STRING,
        "expiry_date": STRING,
        "manufacturing_date": STRING,
        "batch_number": STRING,
        "mrp": STRING,
        "storage_instructions": STRING,
        "prescription_required": {"type": "BOOLEAN"},
        "common_uses": {"type": "ARRAY", "items": STRING},
        "side_effects": {"type": "ARRAY", "items": STRING},
        "barcode": STRING,
        "qr_code": STRING,
        "confidence": {"type": "NUMBER"},
    },
    "required": ["name", "confidence"],
}

# ---------------------------------------------------------------------------
# Prompts (schema JSON only; no free-text output)
# ---------------------------------------------------------------------------

_PRESCRIPTION_PROMPT = (
    "You are a medical image reader for prescriptions.\n"
    "Analyse the uploaded prescription image(s). It may be printed, "
    "handwritten, or mixed printed + handwritten. The photo may be taken "
    "by a mobile camera, rotated, blurred, low-resolution or shadowed - "
    "use your vision understanding to still read the text.\n"
    "Tasks:\n"
    "1. Extract EVERY medicine written on the prescription (never only the "
    "first one).\n"
    "2. For each medicine extract: name, brand (if visible), generic name "
    "(if visible), strength and unit (e.g. '650', 'mg'), dosage (e.g. '1 "
    "tablet'), frequency (e.g. 'twice daily', '1-1-1', 'BD'), timing (e.g. "
    "'after food', 'before breakfast'), duration (e.g. '5 days'), quantity "
    "(e.g. '10 tablets'), route (e.g. 'oral', 'topical') and special "
    "instructions (e.g. 'take with milk').\n"
    "3. Extract the patient name, age and gender, the doctor name, "
    "registration number, hospital/clinic and department, the prescription "
    "date, the disease/diagnosis, symptoms and any doctor notes when "
    "visible.\n"
    "4. Set per-medicine confidence (0-100) and overall confidence (0-100). "
    "When handwriting is uncertain, lower the confidence instead of "
    "guessing.\n"
    "Rules:\n"
    "- If a field is not visible or not legible, return null. NEVER invent "
    "data.\n"
    "- Return ONLY valid JSON matching the schema. No markdown, no "
    "explanation, no text outside JSON."
)

_MEDICINE_PROMPT = (
    "You are a medical image reader for medicine packaging.\n"
    "Analyse the uploaded image of a medicine strip, bottle, sachet, box or "
    "label. The photo may be taken by a mobile camera, rotated, blurred, "
    "low-resolution or shadowed - use your vision understanding to still "
    "read the text.\n"
    "Tasks:\n"
    "1. Extract the medicine name, brand (trade name) and generic name "
    "exactly as printed.\n"
    "2. Extract strength + unit (e.g. '650', 'mg'), medicine type (Tablet / "
    "Capsule / Syrup / Injection / Drops / Ointment / etc.), manufacturer, "
    "expiry date, manufacturing date, batch number and MRP price when "
    "visible.\n"
    "3. Extract storage instructions, whether a prescription is required "
    "(true/false - null if unknown), common uses and side effects ONLY if "
    "they are printed on the packaging (otherwise null).\n"
    "4. If a barcode or QR code is visible, read its exact numeric/alphanumeric "
    "value.\n"
    "5. Set confidence (0-100). When the text is faint, handwritten or "
    "blurred, lower the confidence instead of guessing.\n"
    "Rules:\n"
    "- If a field is not visible or not legible, return null. NEVER invent "
    "data.\n"
    "- Return ONLY valid JSON matching the schema. No markdown, no "
    "explanation, no text outside JSON."
)

# ---------------------------------------------------------------------------
# Image preprocessing (orientation / contrast / sharpness / denoise / compress)
# ---------------------------------------------------------------------------

# Longest edge (px) after downscaling: bounds payload size & latency while
# keeping text readable for the vision model.
MAX_EDGE = 1568
JPEG_QUALITY = 88


def _decode_rgb(data: bytes) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:
        logger.warning("Vision image decode failed: %s", exc)
        return None


def _deskew_vision(img):
    """Correct page/photo rotation so text lines run horizontal."""
    try:
        import cv2

        gray = np.array(img.convert("L"))
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle -= 90
        if abs(angle) < 0.5:
            return img
        h, w = gray.shape
        matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        rotated = cv2.warpAffine(
            gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        return Image.fromarray(rotated).convert("RGB")
    except Exception as exc:
        logger.warning("Vision deskew failed: %s", exc)
        return img


def _enhance_vision(img):
    """Contrast (CLAHE) -> sharpen (unsharp mask) -> denoise (fastNlMeans)."""
    try:
        import cv2

        gray = np.array(img.convert("L"))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrast, (0, 0), 3.0)
        sharpened = cv2.addWeighted(contrast, 1.8, blurred, -0.8, 0)
        denoised = cv2.fastNlMeansDenoising(sharpened, None, 10, 7, 21)
        return Image.fromarray(denoised).convert("RGB")
    except Exception as exc:
        logger.warning("Vision enhancement failed: %s", exc)
        try:
            return (
                ImageEnhance.Contrast(img)
                .enhance(1.3)
                .filter(ImageFilter.UnsharpMask(radius=2, percent=120))
            )
        except Exception:
            return img


def _compress(img) -> bytes:
    """Downscale to MAX_EDGE and encode as high-quality JPEG bytes."""
    w, h = img.size
    longest = max(w, h)
    if longest > MAX_EDGE:
        scale = MAX_EDGE / float(longest)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buf.seek(0)
    return buf.read()


def _preprocess(data: bytes) -> bytes | None:
    """Full preprocessing pipeline: decode -> deskew -> enhance -> compress."""
    img = _decode_rgb(data)
    if img is None:
        return None
    img = _deskew_vision(img)
    img = _enhance_vision(img)
    return _compress(img)


def _image_parts(pages: list[bytes]) -> list[dict]:
    parts = []
    for page in pages:
        encoded = base64.b64encode(page).decode("ascii")
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": encoded}})
    return parts


def _prepare_pages(data: bytes, content_type: str) -> list[bytes] | None:
    """Turn raw upload bytes into preprocessed JPEG page bytes (or None)."""
    try:
        if content_type == "application/pdf":
            from .ocr_service import _render_pdf_pages

            raw_pages = _render_pdf_pages(data)[:_max_pages()]
        else:
            raw_pages = [data]
        pages: list[bytes] = []
        for raw in raw_pages:
            prepped = _preprocess(raw)
            if prepped is None:
                return None
            pages.append(prepped)
        return pages
    except Exception as exc:
        logger.warning("Gemini page preparation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Gemini API call (REST + structured output)
# ---------------------------------------------------------------------------

def _call_gemini(pages: list[bytes], schema: dict, prompt: str) -> dict | None:
    """Send pages to Gemini with structured-output schema. Returns the JSON
    object or None (never raises)."""
    session = _get_session()
    if session is None:
        return None
    settings = _get_settings()
    api_key = settings.GEMINI_API_KEY

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_model_name()}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}, *_image_parts(pages)],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.0,
        },
    }
    headers = {"Content-Type": "application/json"}

    for attempt in (1, 2):  # single retry on transient errors
        try:
            resp = session.post(
                url,
                params={"key": api_key},
                json=payload,
                headers=headers,
                timeout=_timeout(),
            )
        except Exception as exc:
            logger.warning("Gemini Vision request failed (attempt %d): %s", attempt, exc)
            continue

        if resp.status_code == 200:
            return _parse_gemini_response(resp.json())
        if resp.status_code in (429, 500, 502, 503, 504):
            logger.warning("Gemini Vision HTTP %s (attempt %d); retrying.", resp.status_code, attempt)
            continue
        logger.warning("Gemini Vision HTTP %s: %s", resp.status_code, resp.text[:300])
        return None
    return None


def _parse_gemini_response(body: dict) -> dict | None:
    """Pull the model's JSON out of a generateContent response body."""
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Gemini Vision: unexpected response shape.")
        return None
    if not text or not text.strip():
        return None
    return _parse_json(text)


def _parse_json(text: str) -> dict | None:
    """Parse the model's text as JSON, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
            except (ValueError, TypeError):
                logger.warning("Gemini Vision: response was not valid JSON.")
                return None
        else:
            logger.warning("Gemini Vision: response was not valid JSON.")
            return None
    if not isinstance(data, dict):
        logger.warning("Gemini Vision: JSON was not an object.")
        return None
    return data


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _clean(value) -> str:
    """Normalise a schema field: None/number -> '' for display."""
    if value is None:
        return ""
    return str(value).strip()


def _to_confidence(value) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(100.0, max(0.0, c)), 1)


def _canonical_name(name: str) -> str:
    """Prefer the knowledge-base canonical name when the AI name matches."""
    if not name:
        return ""
    kb_matches = kb.find_medicines_extended(name)
    if kb_matches:
        return kb_matches[0]
    return name


# ---------------------------------------------------------------------------
# Public entry points (primary AI)
# ---------------------------------------------------------------------------

def extract_prescription(data: bytes, content_type: str) -> dict | None:
    """Run Gemini Vision on a prescription and return the RAW structured
    payload (with patient/doctor/medicines/confidence), or None when the AI
    cannot be used / produced nothing usable.

    The payload uses the schema's exact field names (name, brand,
    generic_name, ...) and keeps null for unknown fields so downstream code
    (parser) can decide what to surface.
    """
    if not _is_enabled():
        return None
    pages = _prepare_pages(data, content_type)
    if not pages:
        return None
    payload = _call_gemini(pages, PRESCRIPTION_SCHEMA, _PRESCRIPTION_PROMPT)
    if not payload:
        return None
    if not payload.get("medicines"):
        logger.info("Gemini Vision: prescription produced no medicines.")
        return None
    return payload


def extract_medicine(data: bytes, content_type: str) -> dict | None:
    """Run Gemini Vision on a medicine package and return the RAW structured
    payload (name/brand/generic/expiry/barcode/qr/confidence), or None."""
    if not _is_enabled():
        return None
    pages = _prepare_pages(data, content_type)
    if not pages:
        return None
    payload = _call_gemini(pages, MEDICINE_SCHEMA, _MEDICINE_PROMPT)
    if not payload:
        return None
    if not payload.get("name"):
        logger.info("Gemini Vision: medicine produced no name.")
        return None
    return payload


def extract_vision(data: bytes, content_type: str, upload_type: str) -> dict | None:
    """Backward-compatible wrapper used by the legacy gemini_vision shim.

    Returns a fully-formed response dict (same shape as the OCR pipeline)
    built purely from the Gemini payload, or None when the AI cannot be
    used — the caller then falls back to the offline OCR pipeline.
    """
    from .parser import build_from_gemini_only

    payload = (
        extract_prescription(data, content_type)
        if upload_type == "prescription"
        else extract_medicine(data, content_type)
    )
    if payload is None:
        return None
    return build_from_gemini_only(payload, upload_type)
