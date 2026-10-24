"""AI extraction services: Gemini Vision (primary), OCR (fallback), parser (merge).

Architecture (per product spec):

    Upload -> Gemini Vision -> confidence >= 85% -> structured JSON
                             -> confidence <  85% -> run OCR -> merge Gemini + OCR -> final JSON
    Final confidence < 60% -> needs_manual_review: true
"""
