"""OCR fallback engine (RapidOCR, on-device ONNX).

This module is the *engine* used when the primary AI (Gemini Vision) is
disabled, unconfigured, or fails. It contains only OCR/PDF/image helpers and
per-medicine structured extraction — no HTTP, no AI.

Design guarantees:

    1. Never crashes. Every image operation is wrapped; failures return
       empty text / zero confidence so the pipeline can react gracefully.
    2. Real OCR only. Confidence is the mean of RapidOCR word confidences —
       never random.
    3. Handwritten / low-quality support. A second pass runs OCR over the
       original image plus preprocessed variants (deskew, auto-crop,
       brightness normalization, CLAHE, threshold, denoise, 180° rotation)
       and merges all recognised lines.
    4. Anti-hallucination. Every field is extracted strictly from OCR text;
       anything not found stays empty.
"""

from __future__ import annotations

import io
import logging
import threading

import numpy as np
from PIL import Image, ImageOps, ImageStat

from .. import medicine_kb as kb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Below this std-dev the image is effectively blank (white/black/near-uniform).
BLANK_STDDEV_THRESHOLD = 3.0

# Minimum OCR word-confidence to consider extraction reliable.
MIN_WORD_SCORE = 0.3

# Lower floor used on the enhanced (handwritten) OCR pass: faint handwritten
# characters still count towards the confidence score instead of being
# dropped entirely.
HANDWRITTEN_MIN_WORD_SCORE = 0.15

# Confidence threshold (percent) below which status becomes low_confidence.
LOW_CONFIDENCE_THRESHOLD = 60.0

# PDF page render DPI for OCR of scanned prescriptions.
PDF_RENDER_DPI = 200

# ---------------------------------------------------------------------------
# Engine (lazy, thread-safe singleton)
# ---------------------------------------------------------------------------

_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    """Lazily initialise the RapidOCR engine once (thread-safe)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from rapidocr_onnxruntime import RapidOCR

                _engine = RapidOCR()
    return _engine


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _decode_image(data: bytes):
    """Decode raw bytes into a PIL RGB image, or None if invalid.

    EXIF orientation is applied so phone photos that are stored rotated
    (but display correctly) are OCR'd the right way up.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except Exception as exc:
        logger.warning("Image decode failed: %s", exc)
        return None


def _is_blank_image(img) -> bool:
    """Return True if the image is essentially uniform (blank)."""
    try:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        stddev = float(stat.stddev[0])
        logger.info(
            "Blank check: grayscale stddev=%.2f (threshold=%.2f)",
            stddev,
            BLANK_STDDEV_THRESHOLD,
        )
        return stddev < BLANK_STDDEV_THRESHOLD
    except Exception as exc:
        logger.warning("Blank detection failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _extract_pdf_text(data: bytes) -> str:
    """Extract the embedded text layer of a digital PDF (no OCR needed)."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        chunks = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            chunks.append(text)
        return "\n".join(chunks).strip()
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        return ""


def _render_pdf_pages(data: bytes) -> list[bytes]:
    """Render every PDF page to PNG bytes for OCR (scanned PDFs)."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
            pages.append(pix.tobytes("png"))
        return pages
    except Exception as exc:
        logger.warning("PDF rendering failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Image preprocessing (handwritten / low-quality support)
# ---------------------------------------------------------------------------

def _deskew(img):
    """Rotate the image so text lines run horizontal (±0.5° tolerance)."""
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
            angle = angle - 90
        if abs(angle) < 0.5:
            return img
        h, w = gray.shape
        matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        rotated = cv2.warpAffine(
            gray,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        logger.info("Image deskewed by %.2f°.", angle)
        return Image.fromarray(rotated)
    except Exception as exc:
        logger.warning("Deskew failed: %s", exc)
        return img


def _crop_to_content(img, padding: int = 8):
    """Crop the image to its content bounding box (auto-crop)."""
    try:
        import cv2

        gray = np.array(img.convert("L"))
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 50:
            return img
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0)
        h, w = gray.shape
        y0 = max(0, y0 - padding)
        x0 = max(0, x0 - padding)
        y1 = min(h, y1 + padding)
        x1 = min(w, x1 + padding)
        return img.crop((x0, y0, x1, y1))
    except Exception as exc:
        logger.warning("Auto-crop failed: %s", exc)
        return img


def _preprocess_variants(img) -> list:
    """Return enhanced grayscale variants of *img* to help OCR read text.

    Handwritten or low-quality photos often defeat a raw OCR pass. Each
    variant targets a different failure mode (baseline grayscale, contrast
    stretch, CLAHE+sharpen, adaptive threshold, denoised threshold, 180°
    rotation). Returns a list of numpy arrays (or PNG bytes when numpy is
    missing).
    """
    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV unavailable; OCR preprocessing limited.")
        return [np.array(img.convert("L"))]

    deskewed = _deskew(img)
    gray = np.array(deskewed.convert("L"))
    variants = [gray]

    try:
        cropped = _crop_to_content(deskewed)
        cgray = np.array(cropped.convert("L"))
        normalized = cv2.normalize(cgray, None, 0, 255, cv2.NORM_MINMAX)
        variants.append(normalized)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrast, (0, 0), 3.0)
        sharpened = cv2.addWeighted(contrast, 1.8, blurred, -0.8, 0)
        variants.append(sharpened)

        threshold = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 11,
        )
        variants.append(threshold)

        denoised_sharp = cv2.fastNlMeansDenoising(sharpened, None, 10, 7, 21)
        denoised_thresh = cv2.adaptiveThreshold(
            denoised_sharp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 11,
        )
        variants.append(denoised_thresh)

        variants.append(np.ascontiguousarray(np.rot90(gray, 2)))
    except Exception as exc:
        logger.warning("Preprocessing variant generation failed: %s", exc)

    logger.info("Preprocessing completed: %d variant(s) generated.", len(variants))
    return variants


# ---------------------------------------------------------------------------
# OCR runner
# ---------------------------------------------------------------------------

def _run_ocr(data, min_word_score: float = MIN_WORD_SCORE) -> tuple[str, float, list]:
    """Run RapidOCR over raw image bytes or a preprocessed numpy array.

    Returns (full_text, confidence_percent, lines). Confidence is the mean
    word-confidence of OCR-recognised text.
    """
    try:
        engine = _get_engine()
        with _engine_lock:
            result, _elapse = engine(data)
    except Exception as exc:
        logger.error("RapidOCR failed: %s", exc)
        return "", 0.0, []

    if not result:
        logger.info("OCR returned no text regions.")
        return "", 0.0, []

    lines: list[str] = []
    scores: list[float] = []

    for entry in result:
        try:
            text = str(entry[1] or "").strip()
            score = float(entry[2])
        except (IndexError, TypeError, ValueError):
            continue
        if not text:
            continue
        lines.append(text)
        if score >= min_word_score:
            scores.append(score)

    full_text = "\n".join(lines).strip()
    confidence = round((sum(scores) / len(scores) * 100.0), 1) if scores else 0.0

    if full_text and confidence <= 0.0:
        confidence = 1.0

    logger.info(
        "OCR complete: %d lines, %d words scored, confidence=%.1f%%",
        len(lines),
        len(scores),
        confidence,
    )
    return full_text, confidence, lines


def _run_enhanced_ocr(data: bytes, content_type: str, image=None) -> tuple[str, float]:
    """Run OCR over the original image AND every preprocessed variant, then
    merge the recognised lines (deduplicated) into one result.

    Returns (full_text, confidence).
    """
    sources: list = []
    if content_type == "application/pdf":
        pages = _render_pdf_pages(data)
        for page in pages:
            page_img = _decode_image(page)
            if page_img is not None:
                sources.append(page_img)
    elif image is not None:
        sources.append(image)

    merged_lines: list[str] = []
    seen: set[str] = set()
    confidences: list[float] = []
    variant_count = 0

    for src in sources:
        variants = _preprocess_variants(src)
        variant_count += len(variants)
        for variant in variants:
            text, conf, lines = _run_ocr(variant, min_word_score=HANDWRITTEN_MIN_WORD_SCORE)
            if not text or not text.strip():
                continue
            if conf > 0:
                confidences.append(conf)
            for line in lines:
                key = line.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged_lines.append(line.strip())

    merged_text = "\n".join(merged_lines).strip()
    confidence = (
        round(sum(confidences) / len(confidences), 1) if confidences else 0.0
    )

    if merged_text:
        logger.info(
            "Enhanced OCR pass: %d unique line(s) merged across %d variant(s) "
            "(conf=%.1f%%).",
            len(merged_lines),
            variant_count,
            confidence,
        )
    return merged_text, confidence


def run_ocr_on_file(data: bytes, content_type: str, image=None) -> tuple[str, float]:
    """Run OCR over an uploaded file (image or PDF).

    PDFs: digital PDFs return the embedded text layer (confidence 100);
    scanned PDFs are rendered to pages and OCR'd.

    Returns (full_text, confidence).
    """
    if content_type == "application/pdf":
        embedded = _extract_pdf_text(data)
        if embedded.strip():
            logger.info("PDF has embedded text layer; skipping OCR (%d chars).", len(embedded))
            return embedded, 100.0

        pages = _render_pdf_pages(data)
        if not pages:
            return "", 0.0

        all_lines: list[str] = []
        page_confidences: list[float] = []
        for i, page in enumerate(pages):
            text, conf, _lines = _run_ocr(page)
            logger.info("PDF page %d OCR: %d chars, conf=%.1f%%", i + 1, len(text), conf)
            all_lines.append(text)
            if conf > 0:
                page_confidences.append(conf)

        full_text = "\n\n".join(l for l in all_lines if l).strip()
        confidence = (
            round(sum(page_confidences) / len(page_confidences), 1)
            if page_confidences
            else 0.0
        )
        return full_text, confidence

    if image is not None:
        oriented = _deskew(image)
        return _run_ocr(np.array(oriented.convert("L")))[0:2]
    return _run_ocr(data)[0:2]


# ---------------------------------------------------------------------------
# Structured extraction (anti-hallucination)
# ---------------------------------------------------------------------------

def _extract_medicine_entry(text: str, medicine_name: str) -> dict:
    """Build one structured medicine entry strictly from OCR text.

    Every field is populated only if it was actually found in *text*.
    Otherwise the field is returned as "" (frontend renders 'Not Available').

    Dosage/quantity/frequency/duration are read ONLY from the text window
    around this medicine's own token, so a multi-medicine prescription does
    not misattribute the first medicine's details to every entry.
    """
    dosages = kb.find_dosages_near(text, medicine_name)
    quantities = kb.find_quantities_near(text, medicine_name)
    frequencies = kb.find_frequencies_near(text, medicine_name)
    durations = kb.find_durations_near(text, medicine_name)

    dosage = dosages[0] if dosages else ""
    quantity = quantities[0] if quantities else ""
    duration = durations[0] if durations else ""
    freq = ""
    for f in frequencies:
        if len(f.split()) > 1:
            freq = f
            break
    if not freq and frequencies:
        freq = frequencies[0]

    # Timing is derived from the frequency wording (e.g. "after food").
    timing = _infer_timing(freq)

    return {
        "medicine_name": medicine_name,
        "dosage": dosage,
        "quantity": quantity,
        "frequency": freq,
        "duration": duration,
        "timing": timing,
        "brand": "",
        "generic_name": "",
        "strength": "",
        "unit": "",
        "route": "",
        "special_instructions": "",
        "confidence": 0.0,
    }


def _infer_timing(frequency: str) -> str:
    """Derive a human timing hint from a frequency keyword."""
    freq = (frequency or "").lower()
    if "after food" in freq or "after meal" in freq:
        return "After Food"
    if "before food" in freq or "empty stomach" in freq or "before meal" in freq:
        return "Before Food"
    if "morning" in freq:
        return "Morning"
    if "night" in freq or "bedtime" in freq or "dinner" in freq:
        return "Night"
    if "evening" in freq or "dinner" in freq:
        return "Evening"
    return ""


def _merge_ocr_texts(primary: str, secondary: str) -> str:
    """Union two OCR text dumps line-by-line (case-insensitive dedup)."""
    lines: list[str] = []
    seen: set[str] = set()
    for chunk in (primary, secondary):
        for line in (chunk or "").splitlines():
            key = line.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            lines.append(line.strip())
    return "\n".join(lines)


def _ai_spell_correct(text: str) -> list[str]:
    """Optional AI spell-correction pass (OFF unless explicitly enabled)."""
    try:
        from django.conf import settings

        if not getattr(settings, "OCR_AI_CORRECTION_ENABLED", False):
            return []
        from ..ai_validator import AIAssistanceService
    except Exception as exc:
        logger.info("AI spell-correction unavailable: %s", exc)
        return []

    candidates = [
        t for t in kb.normalize(text).split() if kb.is_fuzzy_candidate(t)
    ][:6]
    if not candidates:
        return []

    verified: list[str] = []
    assistant = None
    for tok in candidates:
        try:
            if assistant is None:
                assistant = AIAssistanceService()
            suggestion = assistant.suggest_correction(tok)
        except Exception as exc:
            logger.warning("AI spell-correction failed for '%s': %s", tok, exc)
            continue
        if not suggestion:
            continue
        name = (suggestion.get("suggested_name") or "").strip()
        if not name or name.lower() == tok.lower():
            continue
        kb_matches = kb.find_medicines_extended(name)
        for canon in kb_matches:
            if canon not in verified:
                verified.append(canon)

    if verified:
        logger.info(
            "AI spell-correction verified %d medicine(s): %s", len(verified), verified
        )
    return verified
