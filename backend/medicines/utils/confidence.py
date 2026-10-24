"""Confidence calculation and classification for the AI extraction pipeline.

Implements the product's confidence system:

    * 90-100  -> high   (green)
    * 70-89   -> medium (yellow)
    * < 70    -> low    (red)

Plus the pipeline thresholds:

    * Gemini result with confidence >= GEMINI_ACCEPT_THRESHOLD (85) is
      returned directly as the final structured JSON (no OCR merge).
    * A final confidence below MANUAL_REVIEW_THRESHOLD (60) marks the
      response with ``needs_manual_review: true``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pipeline thresholds
# ---------------------------------------------------------------------------

# Confidence at/above which a Gemini-only result is trusted and returned as-is.
GEMINI_ACCEPT_THRESHOLD = 85.0

# Final confidence below which the response must be manually reviewed.
MANUAL_REVIEW_THRESHOLD = 60.0

# Display bands (user spec: 90-100 green, 70-89 yellow, below 70 red).
HIGH_BAND = 90.0
MEDIUM_BAND = 70.0

# Weights used when blending Gemini + OCR confidences into one final value.
GEMINI_WEIGHT = 0.7
OCR_WEIGHT = 0.3


def clamp_confidence(value) -> float:
    """Normalise any numeric value to a 0-100 confidence percentage."""
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    if conf != conf:  # NaN
        return 0.0
    return round(min(100.0, max(0.0, conf)), 1)


def confidence_level(conf) -> str:
    """Return 'high' | 'medium' | 'low' for a 0-100 confidence value."""
    conf = clamp_confidence(conf)
    if conf >= HIGH_BAND:
        return "high"
    if conf >= MEDIUM_BAND:
        return "medium"
    return "low"


def confidence_color(conf) -> str:
    """Return 'green' | 'yellow' | 'red' for the confidence meter."""
    return {"high": "green", "medium": "yellow", "low": "red"}[
        confidence_level(conf)
    ]


def needs_manual_review(conf) -> bool:
    """True when the final confidence is below the manual-review threshold."""
    return clamp_confidence(conf) < MANUAL_REVIEW_THRESHOLD


def combine_confidences(gemini_conf=None, ocr_conf=None) -> float:
    """Blend Gemini + OCR confidences into one final value.

    * Only Gemini available  -> Gemini value.
    * Only OCR available     -> OCR value.
    * Both available         -> weighted average (Gemini weighted higher,
      since it is the primary image-understanding engine).
    * Neither available      -> 0.0.
    """
    pairs = []
    if gemini_conf is not None and clamp_confidence(gemini_conf) > 0:
        pairs.append((clamp_confidence(gemini_conf), GEMINI_WEIGHT))
    if ocr_conf is not None and clamp_confidence(ocr_conf) > 0:
        pairs.append((clamp_confidence(ocr_conf), OCR_WEIGHT))
    if not pairs:
        return 0.0
    total_weight = sum(w for _, w in pairs)
    blended = sum(c * w for c, w in pairs) / total_weight
    return clamp_confidence(blended)
