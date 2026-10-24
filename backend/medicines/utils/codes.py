"""Barcode / QR detection and decoding helpers.

Decoding strategy (best effort, never crashes):

1. QR codes   -> OpenCV's built-in QRCodeDetector (cv2 is already a
                 dependency of the OCR stack, so no new package needed).
2. 1D barcodes -> pyzbar when available (optional dependency). When pyzbar
                 is not installed the function returns None and the Gemini
                 Vision model (primary engine) is asked to read the barcode
                 digits directly from the image instead.

Every function returns None on any failure so the pipeline can simply
fall back to the AI's reading without crashing.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def decode_qr(data: bytes) -> str | None:
    """Decode a QR code from raw image bytes using OpenCV. Returns the
    decoded string payload or None (not found / undecodable / error)."""
    try:
        import cv2
        import numpy as np

        img = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(img, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        detector = cv2.QRCodeDetector()
        value, points, _ = detector.detectAndDecode(frame)
        if points is None:
            return None
        value = (value or "").strip()
        return value or None
    except Exception as exc:
        logger.warning("QR decode failed: %s", exc)
        return None


def decode_barcode(data: bytes) -> str | None:
    """Decode a 1D barcode from raw image bytes using pyzbar (optional).

    Returns the decoded string, or None when pyzbar is unavailable or no
    barcode could be read. Requires ``pyzbar`` + the system zbar library.
    """
    try:
        from pyzbar import pyzbar

        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        results = pyzbar.decode(img)
        if not results:
            return None
        return (results[0].data or b"").decode("utf-8", errors="replace").strip() or None
    except ImportError:
        # pyzbar not installed -> the AI (primary engine) reads barcodes.
        return None
    except Exception as exc:
        logger.warning("Barcode decode failed: %s", exc)
        return None


def detect_codes(data: bytes) -> dict:
    """Try to decode both a QR code and a barcode from the image bytes.

    Returns::

        {
            "qr_value": str | None,
            "barcode_value": str | None,
        }
    """
    return {
        "qr_value": decode_qr(data),
        "barcode_value": decode_barcode(data),
    }
