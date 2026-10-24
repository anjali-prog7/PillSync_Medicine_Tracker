"""Merge layer for the AI extraction pipeline.

Takes the RAW Gemini Vision payload and the OCR pipeline result and merges
them into ONE final response dict:

    * Deduplicate medicines (normalized-name aware, Gemini wins ties).
    * Fill missing fields from the other source (Gemini primary).
    * Normalize medicine names through the knowledge base.
    * Compute the final confidence via utils/confidence.
    * Decide status / needs_manual_review / confidence_level.
    * Attach packaging extras for medicine uploads (barcode, QR, expiry).
"""

from __future__ import annotations

import logging

from .. import medicine_kb as kb
from ..utils import confidence as conf
from ..utils.codes import detect_codes
from ..utils.expiry import expiry_status

logger = logging.getLogger(__name__)


def _clean(value) -> str:
    """Normalise a field: None/number -> '' for display."""
    if value is None:
        return ""
    return str(value).strip()


def _to_confidence(value) -> float:
    return conf.clamp_confidence(value)


def _normalize_key(name: str) -> str:
    """A stable, case-insensitive key used to dedupe medicine names."""
    n = _clean(name).lower()
    for ch in " -_/.,":
        n = n.replace(ch, "")
    return n


def _canonical_name(name: str) -> str:
    """Prefer the knowledge-base canonical name when it matches."""
    name = _clean(name)
    if not name:
        return ""
    matches = kb.find_medicines_extended(name)
    if matches:
        return matches[0]
    return name


def _gemini_medicine_entry(m: dict) -> dict:
    """Map one raw Gemini medicine object to the final entry shape."""
    name = _canonical_name(m.get("name"))
    return {
        "medicine_name": name,
        "brand": _clean(m.get("brand")),
        "generic_name": _clean(m.get("generic_name")),
        "strength": _clean(m.get("strength")),
        "unit": _clean(m.get("unit")),
        "dosage": _clean(m.get("dosage")) or _clean(m.get("strength")),
        "quantity": _clean(m.get("quantity")),
        "frequency": _clean(m.get("frequency")),
        "timing": _clean(m.get("timing")),
        "duration": _clean(m.get("duration")),
        "route": _clean(m.get("route")),
        "special_instructions": _clean(m.get("special_instructions")),
        "confidence": _to_confidence(m.get("confidence")),
    }


def _ocr_medicine_entry(m: dict) -> dict:
    """Map one OCR medicine entry to the final entry shape."""
    return {
        "medicine_name": _canonical_name(m.get("medicine_name")),
        "brand": _clean(m.get("brand")),
        "generic_name": _clean(m.get("generic_name")),
        "strength": _clean(m.get("strength")),
        "unit": _clean(m.get("unit")),
        "dosage": _clean(m.get("dosage")),
        "quantity": _clean(m.get("quantity")),
        "frequency": _clean(m.get("frequency")),
        "timing": _clean(m.get("timing")),
        "duration": _clean(m.get("duration")),
        "route": _clean(m.get("route")),
        "special_instructions": _clean(m.get("special_instructions")),
        "confidence": _to_confidence(m.get("confidence")),
    }


def _merge_medicine(gemini_entry: dict | None, ocr_entry: dict | None) -> dict:
    """Merge one medicine from both sources. Gemini values win; OCR fills
    only the fields Gemini left empty."""
    base = {
        "medicine_name": "",
        "brand": "",
        "generic_name": "",
        "strength": "",
        "unit": "",
        "dosage": "",
        "quantity": "",
        "frequency": "",
        "timing": "",
        "duration": "",
        "route": "",
        "special_instructions": "",
        "confidence": 0.0,
    }
    if ocr_entry:
        base = {**base, **ocr_entry}
    if gemini_entry:
        base = {**base, **{k: v for k, v in gemini_entry.items() if v}}
    if not base["medicine_name"]:
        base["medicine_name"] = gemini_entry.get("medicine_name", "") if gemini_entry else ""
    return base


def _dedupe_medicines(entries: list[dict]) -> list[dict]:
    """Remove duplicate medicines using the normalized-name key. The first
    (highest-priority) entry for a given name is kept."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    for entry in entries:
        name = entry.get("medicine_name", "")
        if not name:
            continue
        key = _normalize_key(name)
        if key not in seen:
            seen[key] = entry
            order.append(key)
    return [seen[k] for k in order]


def _flatten_str_list(value) -> str:
    """Join a schema list (common_uses / side_effects) into a display string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(_clean(x) for x in value if _clean(x))
    return _clean(value)


def _parse_prescription_fields(payload: dict) -> dict:
    """Pull patient/doctor/date/disease fields out of the raw Gemini
    prescription payload."""
    patient = payload.get("patient") or {}
    doctor = payload.get("doctor") or {}
    return {
        "patient_name": _clean(patient.get("name")) if isinstance(patient, dict) else "",
        "patient_age": _clean(patient.get("age")) if isinstance(patient, dict) else "",
        "patient_gender": _clean(patient.get("gender")) if isinstance(patient, dict) else "",
        "doctor_name": _clean(doctor.get("name")) if isinstance(doctor, dict) else "",
        "doctor_registration": _clean(doctor.get("registration_number")) if isinstance(doctor, dict) else "",
        "hospital": _clean(doctor.get("hospital")) if isinstance(doctor, dict) else "",
        "department": _clean(doctor.get("department")) if isinstance(doctor, dict) else "",
        "prescription_date": _clean(payload.get("prescription_date")),
        "disease": _clean(payload.get("disease")),
        "diagnosis": _clean(payload.get("diagnosis")),
        "symptoms": _clean(payload.get("symptoms")),
        "doctor_notes": _clean(payload.get("doctor_notes")),
    }


def _extract_ocr_fields(result: dict) -> dict:
    """Pull legacy OCR fields into the final response shape."""
    return {
        "patient_name": _clean(result.get("patient_name")),
        "patient_age": _clean(result.get("patient_age")),
        "patient_gender": _clean(result.get("patient_gender")),
        "doctor_name": _clean(result.get("doctor_name")),
        "doctor_registration": _clean(result.get("doctor_registration")),
        "hospital": _clean(result.get("hospital")),
        "department": _clean(result.get("department")),
        "prescription_date": _clean(result.get("prescription_date")),
        "disease": _clean(result.get("disease")),
        "diagnosis": _clean(result.get("diagnosis")),
        "symptoms": _clean(result.get("symptoms")),
        "doctor_notes": _clean(result.get("doctor_notes")),
    }


def build_from_gemini_only(payload: dict, upload_type: str) -> dict:
    """Build a fully-formed response from the Gemini payload alone
    (confidence >= 85% path)."""
    return merge_results(payload, None, upload_type)


def merge_results(gemini_payload: dict | None, ocr_result: dict | None, upload_type: str) -> dict:
    """Merge the Gemini payload and the OCR result into the final response.

    Args:
        gemini_payload: raw payload from services.gemini_service (or None).
        ocr_result: response dict from the OCR pipeline (or None).
        upload_type: 'prescription' | 'medicine'.
    """
    gemini_conf = _to_confidence(gemini_payload.get("confidence")) if gemini_payload else 0.0
    ocr_conf = _to_confidence(ocr_result.get("confidence")) if ocr_result else 0.0

    # ---- medicines ----------------------------------------------------
    gemini_meds = [_gemini_medicine_entry(m) for m in (gemini_payload or {}).get("medicines") or []]
    ocr_meds = [_ocr_medicine_entry(m) for m in (ocr_result or {}).get("medicines") or []]

    # Merge each Gemini medicine with its OCR counterpart (by normalized name).
    ocr_by_key = {_normalize_key(m["medicine_name"]): m for m in ocr_meds if m["medicine_name"]}
    merged = []
    for g in gemini_meds:
        merged.append(_merge_medicine(g, ocr_by_key.get(_normalize_key(g["medicine_name"]))))
    # OCR-only medicines that Gemini did not find.
    gemini_keys = {_normalize_key(g["medicine_name"]) for g in gemini_meds}
    for o in ocr_meds:
        if _normalize_key(o["medicine_name"]) not in gemini_keys:
            merged.append(_merge_medicine(None, o))

    if not merged:
        # Only a primary medicine at the top level (medicine-strip style).
        if upload_type == "medicine" and gemini_payload and gemini_payload.get("name"):
            merged = [_gemini_medicine_entry(gemini_payload)]
        elif upload_type == "medicine" and ocr_result and ocr_result.get("medicine_name"):
            merged = [_ocr_medicine_entry({"medicine_name": ocr_result.get("medicine_name"), **ocr_result})]

    medicines = _dedupe_medicines(merged)

    # ---- top-level fields ---------------------------------------------
    pres_fields = _parse_prescription_fields(gemini_payload) if gemini_payload else _extract_ocr_fields(ocr_result or {})

    patient_name = pres_fields["patient_name"]
    doctor_name = pres_fields["doctor_name"]
    hospital = pres_fields["hospital"]
    disease = pres_fields["disease"] or pres_fields["diagnosis"]
    date = pres_fields["prescription_date"]

    # Build prescription_details (structured summary, never a raw dump).
    details = _build_summary(
        medicines,
        patient=patient_name,
        doctor=doctor_name,
        hospital=hospital,
        disease=disease,
        date=date,
        doctor_notes=pres_fields["doctor_notes"],
        symptoms=pres_fields["symptoms"],
    )

    # ---- packaging extras (medicine uploads) --------------------------
    barcode_value = ""
    qr_value = ""
    expiry = None
    medicine_details = {}
    if upload_type == "medicine":
        if gemini_payload:
            barcode_value = _clean(gemini_payload.get("barcode"))
            qr_value = _clean(gemini_payload.get("qr_code"))
            medicine_details = {
                "medicine_type": _clean(gemini_payload.get("medicine_type")),
                "manufacturer": _clean(gemini_payload.get("manufacturer")),
                "expiry_date": _clean(gemini_payload.get("expiry_date")),
                "manufacturing_date": _clean(gemini_payload.get("manufacturing_date")),
                "batch_number": _clean(gemini_payload.get("batch_number")),
                "mrp": _clean(gemini_payload.get("mrp")),
                "storage_instructions": _clean(gemini_payload.get("storage_instructions")),
                "prescription_required": gemini_payload.get("prescription_required"),
                "common_uses": _flatten_str_list(gemini_payload.get("common_uses")),
                "side_effects": _flatten_str_list(gemini_payload.get("side_effects")),
            }
            if medicine_details["expiry_date"]:
                expiry = expiry_status(medicine_details["expiry_date"])

    # ---- confidence ---------------------------------------------------
    final_conf = conf.combine_confidences(gemini_conf, ocr_conf)
    if final_conf == 0.0 and medicines:
        per_med = [m["confidence"] for m in medicines if m.get("confidence")]
        final_conf = conf.clamp_confidence(sum(per_med) / len(per_med)) if per_med else 60.0

    needs_review = conf.needs_manual_review(final_conf)
    engine = "gemini" if gemini_payload and not ocr_result else ("merged" if gemini_payload else "ocr")

    if gemini_payload is None:
        # OCR-only path: preserve the OCR pipeline's own status/message so
        # legacy behaviour (success vs low_confidence vs no_medicine) is
        # exactly as before. Only needs_manual_review is added.
        status = (ocr_result or {}).get("status", "no_medicine")
        message = (ocr_result or {}).get("message", "")
        if not status and medicines:
            status, message = _decide_status(final_conf, needs_review, True)
    else:
        status, message = _decide_status(final_conf, needs_review, bool(medicines))

    # Primary medicine = first entry (strip) or first prescription med.
    primary = medicines[0] if medicines else {}

    return {
        "status": status,
        "message": message,
        "needs_manual_review": needs_review,
        "confidence": final_conf,
        "confidence_level": conf.confidence_level(final_conf),
        "confidence_color": conf.confidence_color(final_conf),
        "engine": engine,
        "upload_type": upload_type,
        # Legacy flat keys (frontend continues to render these).
        "medicine_name": primary.get("medicine_name", "") or (ocr_result or {}).get("medicine_name", ""),
        "dosage": primary.get("dosage", "") or (ocr_result or {}).get("dosage", ""),
        "quantity": primary.get("quantity", "") or (ocr_result or {}).get("quantity", ""),
        "frequency": primary.get("frequency", "") or (ocr_result or {}).get("frequency", ""),
        "doctor_name": doctor_name,
        "hospital": hospital,
        "disease": disease,
        "prescription_date": date,
        "prescription_details": details,
        "medicines": medicines,
        "raw_text": _clean((ocr_result or {}).get("raw_text")),
        # Rich fields for the redesigned result view.
        "patient": {
            "name": patient_name,
            "age": pres_fields["patient_age"],
            "gender": pres_fields["patient_gender"],
        },
        "doctor": {
            "name": doctor_name,
            "registration_number": pres_fields["doctor_registration"],
            "hospital": hospital,
            "department": pres_fields["department"],
        },
        "diagnosis": pres_fields["diagnosis"],
        "symptoms": pres_fields["symptoms"],
        "doctor_notes": pres_fields["doctor_notes"],
        "barcode": barcode_value,
        "qr_code": qr_value,
        "expiry": expiry,
        "medicine_details": medicine_details or None,
        "gemini_result": gemini_payload,
        "ocr_text": _clean((ocr_result or {}).get("raw_text"))[:2000],
    }


def _decide_status(final_conf: float, needs_review: bool, has_medicines: bool) -> tuple[str, str]:
    """Map confidence to status/message."""
    if not has_medicines:
        return (
            "no_medicine",
            "No medicine detected in uploaded image. Please try a clearer photo or enter the details manually.",
        )
    if needs_review:
        return (
            "low_confidence",
            "Extraction confidence is below 60% — please review the extracted details manually before saving.",
        )
    if final_conf < conf.GEMINI_ACCEPT_THRESHOLD:
        return (
            "low_confidence",
            "Extraction confidence is moderate — please review the extracted details before saving.",
        )
    return ("success", "Medicine detected and extracted.")


def _build_summary(
    medicines,
    patient="",
    doctor="",
    hospital="",
    disease="",
    date="",
    doctor_notes="",
    symptoms="",
) -> str:
    """Build a human-readable structured summary (never the raw OCR dump)."""
    lines = []
    if patient:
        lines.append(f"Patient: {patient}")
    if doctor:
        lines.append(f"Doctor: {doctor}")
    if hospital:
        lines.append(f"Hospital: {hospital}")
    if date:
        lines.append(f"Date: {date}")
    if disease:
        lines.append(f"Disease: {disease}")
    if symptoms:
        lines.append(f"Symptoms: {symptoms}")
    if doctor_notes:
        lines.append(f"Notes: {doctor_notes}")
    if medicines:
        lines.append("Medicines:")
        for m in medicines:
            parts = [m.get("medicine_name", "")]
            if m.get("dosage"):
                parts.append(m["dosage"])
            if m.get("frequency"):
                parts.append(m["frequency"])
            if m.get("duration"):
                parts.append(f"{m['duration']}")
            lines.append("• " + " ".join(p for p in parts if p))
    return "\n".join(lines)
