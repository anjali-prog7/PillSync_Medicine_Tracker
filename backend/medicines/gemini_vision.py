"""Legacy compatibility shim for the Gemini Vision extraction module.

The production Gemini engine now lives in ``services/gemini_service.py``
(primary AI) with the ``extract_prescription()`` / ``extract_medicine()``
entry points. This module keeps the old ``extract_vision()`` import path
working for anything that still references it.
"""

from .services.gemini_service import (  # noqa: F401
    extract_medicine,
    extract_prescription,
    extract_vision,
)

__all__ = ["extract_medicine", "extract_prescription", "extract_vision"]
