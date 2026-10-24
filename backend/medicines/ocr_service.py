"""Prescription / medicine upload pipeline (orchestration facade).

Implements the product architecture:

    Upload -> Gemini Vision (PRIMARY AI)
              |-- confidence >= 85%  -> return structured JSON directly
              |-- confidence <  85%  -> run OCR (RapidOCR fallback)
                                         -> merge Gemini + OCR (parser)
                                         -> return final JSON
    Final confidence < 60% -> needs_manual_review: true

The OCR engine itself lives in ``services/ocr_service.py``, the Gemini
engine in ``services/gemini_service.py`` and the merge logic in
``services/parser.py``. This module keeps the public API stable
(``process_upload`` and the OCR helpers) so existing views and tests
keep working unchanged.

Anti-hallucination guarantees:
    - Gemini never invents data (schema instructs null for unknown fields).
    - OCR fields are returned ONLY if present in the recognised text.
    - Non-medical / blank images are rejected with status "no_medicine".
"""

from __future__ import annotations

import logging

from .services import ocr_service as ocr_engine
from .services.parser import merge_results
from .utils import confidence as conf

logger = logging.getLogger(__name__)

# Re-export the OCR engine's public surface so imports keep working:
#   from .ocr_service import process_upload, run_ocr_on_file, ...
from .services.ocr_service import (  # noqa: F401
    BLANK_STDDEV_THRESHOLD,
    HANDWRITTEN_MIN_WORD_SCORE,
    LOW_CONFIDENCE_THRESHOLD,
    MIN_WORD_SCORE,
    PDF_RENDER_DPI,
    _ai_spell_correct,
    _decode_image,
    _extract_medicine_entry,
    _get_engine,
    _infer_timing,
    _is_blank_image,
    _merge_ocr_texts,
    _preprocess_variants,
    _run_enhanced_ocr,
    _run_ocr,
    run_ocr_on_file,
)


def _no_medicine_response(message: str) -> dict:
    """Standard response for rejected uploads."""
    return {
        "status": "no_medicine",
        "message": message,
        "medicine_name": "", "dosage": "", "quantity": "",
        "frequency": "", "doctor_name": "", "hospital": "",
        "prescription_date": "", "disease": "", "prescription_details": "",
        "confidence": 0, "medicines": [], "raw_text": "",
    }


def _low_confidence_response(message: str, raw_text: str = "") -> dict:
    """Response when OCR read medical text but no medicine name could be
    verified — a Low Confidence Extraction the user can review, never a
    hard rejection."""
    return {
        "status": "low_confidence",
        "message": message,
        "medicine_name": "", "dosage": "", "quantity": "",
        "frequency": "", "doctor_name": "", "hospital": "",
        "prescription_date": "", "disease": "", "prescription_details": "",
        "confidence": 0, "medicines": [], "raw_text": raw_text,
    }


# ---------------------------------------------------------------------------
# OCR-only pipeline (kept intact so the fallback behaves exactly as before)
# ---------------------------------------------------------------------------

def _run_ocr_pipeline(data: bytes, content_type: str, upload_type: str) -> dict:
    """Run the offline RapidOCR pipeline and return its response dict.

    This is the fallback path when Gemini is disabled/unavailable or its
    confidence is too low to trust alone. Logic is identical to the legacy
    pipeline (decode -> blank check -> OCR pass 1 -> enhanced pass 2 ->
    KB matching -> structured fields).
    """
    image = None
    if content_type != "application/pdf":
        image = _decode_image(data)
        if image is None:
            return {
                "status": "error",
                "message": "The uploaded file is not a valid image.",
                "medicine_name": "", "dosage": "", "quantity": "",
                "frequency": "", "doctor_name": "", "hospital": "",
                "prescription_date": "", "disease": "", "prescription_details": "",
                "confidence": 0, "medicines": [], "raw_text": "",
            }
        if _is_blank_image(image):
            logger.info("Blank image rejected (upload_type=%s).", upload_type)
            return _no_medicine_response(
                "No medicine detected in uploaded image. The image appears to be blank."
            )

    # -- Real OCR (first pass on the original image) --
    text, confidence = run_ocr_on_file(data, content_type, image)
    medicines = _find_medicines(text) if text else []
    logger.info(
        "OCR pass 1 complete: %d chars, confidence=%.1f%%, medicines=%s.",
        len(text or ""),
        confidence,
        medicines,
    )

    # -- Second OCR pass (handwritten / low-quality / low confidence) ----
    handwritten = False
    if not medicines or (confidence > 0 and confidence < LOW_CONFIDENCE_THRESHOLD):
        enhanced_text, enhanced_conf = _run_enhanced_ocr(data, content_type, image)
        if enhanced_text and enhanced_text.strip():
            logger.info(
                "OCR pass 2 recovered %d chars, conf=%.1f%% (upload_type=%s).",
                len(enhanced_text),
                enhanced_conf,
                upload_type,
            )
            merged = _merge_ocr_texts(text, enhanced_text)
            text = merged if merged.strip() else enhanced_text
            if confidence and enhanced_conf:
                confidence = round((confidence + enhanced_conf) / 2.0, 1)
            elif enhanced_conf:
                confidence = enhanced_conf
            medicines = _find_medicines(text)
            handwritten = bool(medicines)
            logger.info(
                "Merged OCR confidence=%.1f%%, medicines after pass 2=%s.",
                confidence,
                medicines,
            )

    # -- Empty OCR -> stop. Never send empty text to AI. --
    if not text or not text.strip():
        logger.info("Empty OCR text rejected (upload_type=%s).", upload_type)
        return _no_medicine_response("No medicine detected in uploaded image.")

    # -- Medicine extraction (production-grade matching pipeline) --------
    matches = _find_all_matches(text)
    medicines = [m["name"] for m in matches]
    primary = matches[0]["name"] if matches else None
    logger.info(
        "Medicine matching: exact=%s merged=%s fuzzy=%s (text chars=%d).",
        [m["name"] for m in matches if m["type"] == "exact"],
        [m["name"] for m in matches if m["type"] == "merged"],
        [m["name"] for m in matches if m["type"] == "fuzzy"],
        len(text),
    )

    if not medicines:
        # Optional AI spell-correction (off by default; never blocks).
        ai_verified = _ai_spell_correct(text)
        if ai_verified:
            medicines = ai_verified
            primary = ai_verified[0]
            handwritten = True
            logger.info("AI spell-correction verified medicines=%s.", ai_verified)

    if not medicines:
        if not _looks_like_medical_text(text):
            logger.info(
                "Final decision: no_medicine (no KB match & no medical text; upload_type=%s).",
                upload_type,
            )
            return _no_medicine_response("No medicine detected in uploaded image.")
        logger.info(
            "Final decision: low_confidence (medical text present, medicine "
            "name unverified; upload_type=%s).",
            upload_type,
        )
        return _low_confidence_response(
            "Low Confidence Extraction: the image contains medical text, "
            "but no medicine name could be verified automatically. "
            "Please review the extracted text below or enter the medicine manually.",
            raw_text=_clean_ocr_text(text)[:2000],
        )

    # -- Structured fields (only from OCR text) --
    doctors = _find_doctors(text)
    hospitals = _find_hospitals(text)
    diseases = _find_diseases(text)
    dates = _find_dates(text)
    patients = _find_patients(text)

    medicine_entries = [_extract_medicine_entry(text, m) for m in medicines]

    status = "success"
    message = "Medicine detected and extracted."
    if handwritten:
        status = "low_confidence"
        message = (
            "Medicine detected from a handwritten or low-quality prescription. "
            "Please review the extracted details."
        )
    elif confidence < LOW_CONFIDENCE_THRESHOLD:
        status = "low_confidence"
        message = "Medicine detected, but OCR confidence is low. Please review the extracted details."

    summary = _build_prescription_summary(
        text,
        medicine_entries,
        doctor=doctors[0] if doctors else "",
        hospital=hospitals[0] if hospitals else "",
        patient=patients[0] if patients else "",
        disease=diseases[0] if diseases else "",
    )
    details = summary[:2000]

    logger.info(
        "Final decision: status=%s, primary=%s, medicines=%d, confidence=%.1f%% "
        "(upload_type=%s).",
        status,
        primary,
        len(medicine_entries),
        confidence,
        upload_type,
    )

    return {
        "status": status,
        "message": message,
        "medicine_name": primary,
        "dosage": medicine_entries[0]["dosage"] if medicine_entries else "",
        "quantity": medicine_entries[0]["quantity"] if medicine_entries else "",
        "frequency": medicine_entries[0]["frequency"] if medicine_entries else "",
        "doctor_name": doctors[0] if doctors else "",
        "hospital": hospitals[0] if hospitals else "",
        "disease": diseases[0] if diseases else "",
        "prescription_date": dates[0] if dates else "",
        "prescription_details": details,
        "confidence": confidence,
        "medicines": medicine_entries,
        "raw_text": _clean_ocr_text(text)[:2000],
        "upload_type": upload_type,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_upload(data: bytes, content_type: str, upload_type: str = "medicine") -> dict:
    """Full AI extraction pipeline.

    Architecture:
        1. Gemini Vision (primary AI) understands the image.
        2. Gemini confidence >= 85% -> return structured JSON (Gemini only).
        3. Gemini confidence < 85%  -> run OCR, merge Gemini + OCR.
        4. Gemini unavailable       -> run OCR alone (legacy behaviour).
        5. Final confidence < 60%   -> needs_manual_review: true.
    """
    # -- 1. Gemini Vision (primary) -------------------------------------
    gemini_payload = None
    try:
        from .services.gemini_service import extract_medicine, extract_prescription

        if upload_type == "prescription":
            gemini_payload = extract_prescription(data, content_type)
        else:
            gemini_payload = extract_medicine(data, content_type)
    except Exception as exc:
        logger.warning(
            "Gemini Vision extraction failed; falling back to OCR: %s", exc
        )
        gemini_payload = None

    if gemini_payload is not None:
        gemini_conf = conf.clamp_confidence(gemini_payload.get("confidence"))
        logger.info(
            "Gemini Vision succeeded (upload_type=%s, confidence=%.1f%%).",
            upload_type,
            gemini_conf,
        )
        if gemini_conf >= conf.GEMINI_ACCEPT_THRESHOLD:
            # -- 2. High confidence -> trust the AI result directly. -------
            logger.info("Gemini confidence >= 85%%; returning structured JSON directly.")
            return merge_results(gemini_payload, None, upload_type)

        # -- 3. Low/moderate confidence -> run OCR and merge. --------------
        logger.info("Gemini confidence < 85%%; running OCR fallback + merge.")
        ocr_result = _run_ocr_pipeline(data, content_type, upload_type)
        return merge_results(gemini_payload, ocr_result, upload_type)

    # -- 4. Gemini unavailable -> OCR alone (legacy behaviour). ----------
    logger.info("Gemini Vision unavailable; using OCR pipeline.")
    ocr_result = _run_ocr_pipeline(data, content_type, upload_type)
    return merge_results(None, ocr_result, upload_type)


# ---------------------------------------------------------------------------
# Knowledge-base delegates (thin wrappers so tests keep passing unchanged)
# ---------------------------------------------------------------------------

def _find_medicines(text: str):
    from . import medicine_kb as kb

    return kb.find_medicines_extended(text)


def _find_all_matches(text: str):
    from . import medicine_kb as kb

    return kb.find_all_matches(text)


def _looks_like_medical_text(text: str) -> bool:
    from . import medicine_kb as kb

    return kb.looks_like_medical_text(text)


def _clean_ocr_text(text: str) -> str:
    from . import medicine_kb as kb

    return kb.clean_ocr_text(text)


def _find_doctors(text: str):
    from . import medicine_kb as kb

    return kb.find_doctors(text)


def _find_hospitals(text: str):
    from . import medicine_kb as kb

    return kb.find_hospitals(text)


def _find_diseases(text: str):
    from . import medicine_kb as kb

    return kb.find_diseases(text)


def _find_dates(text: str):
    from . import medicine_kb as kb

    return kb.find_dates(text)


def _find_patients(text: str):
    from . import medicine_kb as kb

    return kb.find_patients(text)


def _build_prescription_summary(text, entries, doctor="", hospital="", patient="", disease=""):
    from . import medicine_kb as kb

    return kb.build_prescription_summary(
        text, entries, doctor=doctor, hospital=hospital, patient=patient, disease=disease
    )
