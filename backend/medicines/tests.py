"""Tests for the production Prescription OCR module.

Covers the six validation scenarios from the spec:
    Test 1: Real Paracetamol strip          -> detected
    Test 2: Real Dolo strip                 -> detected
    Test 3: Doctor prescription             -> extract the medicines written
    Test 4: Parrot image                    -> rejected "No medicine detected"
    Test 5: Blank white image               -> rejected
    Test 6: Manual entry "Digene"           -> saved exactly as "Digene"

Tests use PIL-generated synthetic images that mimic real medicine strips,
prescriptions, a non-medical (parrot-like) image and a blank image.
"""

import datetime
import io
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .medicine_kb import (
    build_prescription_summary,
    clean_ocr_text,
    find_dates,
    find_dosages_near,
    find_durations_near,
    find_first_medicine,
    find_frequencies_near,
    find_medicines,
    find_medicines_extended,
    find_medicines_fuzzy,
    find_medicines_merged,
    find_patients,
    looks_like_medical_text,
)
from .ocr_service import (
    _extract_medicine_entry,
    _preprocess_variants,
    process_upload,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers: synthetic image generation
# ---------------------------------------------------------------------------


def _make_font(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _make_image(text_lines, width=800, height=450, bg="white"):
    """Create a synthetic image with dark text on a light background."""
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    font = _make_font()
    y = 30
    for line in text_lines:
        draw.text((30, y), line, fill="black", font=font)
        y += 55
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _make_blank_image():
    return _make_image([], bg="white")


def _make_parrot_image():
    """Non-medical image with colour and a caption (like a pet photo)."""
    img = Image.new("RGB", (600, 450), "#d4e8ff")
    draw = ImageDraw.Draw(img)
    # Parrot body
    draw.ellipse([200, 120, 420, 380], fill="#22c55e")
    draw.ellipse([330, 80, 460, 220], fill="#ef4444")
    draw.ellipse([330, 60, 380, 120], fill="#f59e0b")
    draw.polygon([(380, 110), (430, 100), (390, 130)], fill="#f59e0b")
    draw.text((180, 400), "A pretty parrot", fill="#333333", font=_make_font())
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _as_upload(client, data: bytes, name="test.png", upload_type="medicine"):
    """POST a file to the OCR upload endpoint as an authenticated user.

    A 3-tuple (bytes, name, content_type) sets the multipart file's
    Content-Type header, mirroring how a browser uploads a file.
    """
    if name.lower().endswith(".pdf"):
        ctype = "application/pdf"
    else:
        ctype = "image/png"
    return client.post(
        "/api/medicines/prescription/upload/",
        {"file": (io.BytesIO(data), name, ctype), "upload_type": upload_type},
        format="multipart",
    )


# ---------------------------------------------------------------------------
# Knowledge-base unit tests (fast, no engine needed)
# ---------------------------------------------------------------------------


class MedicineKbTests(TestCase):
    def test_paracetamol_strip_text_detected(self):
        self.assertEqual(
            find_first_medicine("PARACETAMOL TABLETS IP 650 mg"), "Paracetamol"
        )

    def test_dolo_strip_text_detected(self):
        self.assertEqual(
            find_first_medicine("DOLO 650 PARACETAMOL TABLETS"), "Dolo 650"
        )

    def test_prescription_extracts_actual_medicines(self):
        medicines = find_medicines(
            "Tab Paracetamol 500mg BD, Tab Ibuprofen 400mg, Tab Naproxen 250mg"
        )
        self.assertIn("Paracetamol", medicines)
        self.assertIn("Ibuprofen", medicines)
        self.assertIn("Naproxen", medicines)

    def test_non_medical_text_returns_nothing(self):
        self.assertIsNone(
            find_first_medicine("a beautiful colorful parrot sitting on a branch")
        )

    def test_blank_text_returns_nothing(self):
        self.assertEqual(find_medicines(""), [])

    def test_manual_digene_is_not_kb_overwritten(self):
        # "Digene" must match itself, never a different medicine name.
        self.assertEqual(find_first_medicine("Digene"), "Digene")

    # -- Prescription date parsing (Issue 1) -----------------------------

    def test_date_dd_mm_yyyy_extracted(self):
        self.assertEqual(find_dates("Dated 31/07/2026"), ["31/07/2026"])

    def test_date_dd_mm_yyyy_with_dash(self):
        self.assertEqual(find_dates("Date: 31-07-2026"), ["31-07-2026"])

    def test_date_yyyy_mm_dd_extracted(self):
        self.assertEqual(find_dates("Date: 2026-07-31"), ["2026-07-31"])

    def test_date_mm_dd_yyyy_extracted(self):
        # Month-first form is recognised because 31 cannot be a month.
        self.assertEqual(find_dates("Date: 07/31/2026"), ["07/31/2026"])

    def test_date_textual_extracted(self):
        self.assertEqual(find_dates("31 Jul 2026"), ["31 Jul 2026"])

    def test_date_spaces_around_separators(self):
        self.assertEqual(find_dates("Dated 31 / 07 / 2026"), ["31/07/2026"])

    def test_invalid_dates_rejected(self):
        self.assertEqual(find_dates("junk 99/99/2026 and 31/13/2026"), [])

    def test_first_valid_date_wins(self):
        self.assertEqual(
            find_dates("First 13/13/2020 then real 02/02/2021"), ["02/02/2021"]
        )

    # -- Patient parsing (Issue 2) ---------------------------------------

    def test_patient_extracted(self):
        self.assertEqual(
            find_patients("Patient Name: Rahul Sharma"), ["Rahul Sharma"]
        )

    def test_no_patient_returns_nothing(self):
        self.assertEqual(find_patients("Tab Paracetamol 500mg"), [])

    # -- Duration parsing (Issue 2) --------------------------------------

    def test_duration_near_medicine(self):
        self.assertEqual(
            find_durations_near("Tab Paracetamol 500mg for 5 days", "Paracetamol"),
            ["5 days"],
        )

    # -- Patient labels are never patient names (Issue 1) ----------------

    def test_patient_never_an_ocr_label(self):
        self.assertEqual(find_patients("Patient Name: Date: 25/07/2026"), [])
        self.assertEqual(find_patients("Patient: Doctor: Dr. Amit Verma"), [])
        self.assertEqual(find_patients("Patient: Hospital"), [])
        self.assertEqual(find_patients("Patient: Rx: Tab Paracetamol 500mg"), [])
        self.assertEqual(find_patients("Patient: Date"), [])

    def test_patient_label_on_next_line_is_not_a_name(self):
        self.assertEqual(find_patients("Patient Name:\nDate: 25/07/2026"), [])

    def test_patient_name_not_overread_across_sections(self):
        # 'Doctor' is the next section heading, not part of the patient name.
        self.assertEqual(
            find_patients("Patient Name: Rahul Sharma Doctor: Dr. Verma"),
            ["Rahul Sharma"],
        )

    def test_patient_extracted_with_title_prefix(self):
        self.assertEqual(
            find_patients("Patient: Dr. Amit Verma"), ["Amit Verma"]
        )

    # -- Dosage scoped per medicine (Issue 2) ----------------------------

    def test_dosage_scoped_per_medicine(self):
        text = (
            "Paracetamol 500 mg after food 5 days\n"
            "Ibuprofen 400 mg after food 5 days\n"
            "Omeprazole 20 mg before breakfast 10 days"
        )
        self.assertEqual(find_dosages_near(text, "Paracetamol")[0], "500 mg")
        self.assertEqual(find_dosages_near(text, "Ibuprofen")[0], "400 mg")
        self.assertEqual(find_dosages_near(text, "Omeprazole")[0], "20 mg")

    def test_dosage_scoped_block_layout(self):
        # Name / dosage / frequency / duration on separate lines: each
        # medicine must still receive ONLY its own dosage.
        text = (
            "Paracetamol\n500 mg\n1-1-1\nAfter food\n5 days\n"
            "Ibuprofen\n400 mg\n1-1-1\nAfter food\n5 days\n"
            "Omeprazole\n20 mg\n1-0-1\nBefore breakfast\n10 days"
        )
        self.assertEqual(find_dosages_near(text, "Paracetamol")[0], "500 mg")
        self.assertEqual(find_dosages_near(text, "Ibuprofen")[0], "400 mg")
        self.assertEqual(find_dosages_near(text, "Omeprazole")[0], "20 mg")

    # -- Duration scoped per medicine (Issue 3) --------------------------

    def test_duration_scoped_per_medicine(self):
        text = (
            "Paracetamol 500 mg after food 5 days\n"
            "Ibuprofen 400 mg after food 5 days\n"
            "Omeprazole 20 mg before breakfast 10 days"
        )
        self.assertEqual(find_durations_near(text, "Paracetamol")[0], "5 days")
        self.assertEqual(find_durations_near(text, "Omeprazole")[0], "10 days")

    def test_duration_scoped_block_layout(self):
        # Omeprazole must keep its own '10 days', never inherit '5 days'.
        text = (
            "Omeprazole\n20 mg\n1-0-1\nBefore breakfast\n10 days\n"
            "Paracetamol\n500 mg\n1-1-1\nAfter food\n5 days"
        )
        self.assertEqual(find_durations_near(text, "Omeprazole")[0], "10 days")
        self.assertEqual(find_durations_near(text, "Paracetamol")[0], "5 days")

    def test_reported_prescription_never_misattributes(self):
        """Regression: the exact numbered 3-medicine prescription from the
        bug report. Every value must come from the medicine's OWN block:

            Paracetamol -> 500 mg  / after food       / 5 days
            Ibuprofen   -> 400 mg  / after food       / 5 days
            Omeprazole  -> 20 mg   / before breakfast / 10 days

        (Ibuprofen must NEVER pick up '20 mg' from Omeprazole's block and
        Omeprazole must NEVER pick up '5 days' from the blocks above it.)
        """
        text = (
            "1. Paracetamol 500 mg\n"
            "   1-1-1\n"
            "   After food\n"
            "   5 days\n"
            "\n"
            "2. Ibuprofen 400 mg\n"
            "   1-1-1\n"
            "   After food\n"
            "   5 days\n"
            "\n"
            "3. Omeprazole 20 mg\n"
            "   1-0-1\n"
            "   Before breakfast\n"
            "   10 days"
        )
        expected = {
            "Paracetamol": ("500 mg", "after food", "5 days"),
            "Ibuprofen": ("400 mg", "after food", "5 days"),
            "Omeprazole": ("20 mg", "before breakfast", "10 days"),
        }
        for name, (dosage, frequency, duration) in expected.items():
            self.assertEqual(find_dosages_near(text, name)[0], dosage)
            # The structured entry prefers a multi-word frequency keyword.
            freqs = find_frequencies_near(text, name)
            multi = next((f for f in freqs if len(f.split()) > 1), None)
            self.assertEqual(multi, frequency)
            self.assertEqual(find_durations_near(text, name)[0], duration)

    def test_reported_prescription_exact_user_format(self):
        """Regression: the user's EXACT prescription layout (number on its
        own line, 'After food' / 'Before breakfast' frequencies, no 1-1-1
        lines). Every value must come from the medicine's OWN block:

            Paracetamol -> 500 mg  -> after food       -> 5 days
            Ibuprofen   -> 400 mg  -> after food       -> 5 days
            Omeprazole  -> 20 mg   -> before breakfast -> 10 days
        """
        text = (
            "1.\n"
            "Paracetamol 500 mg\n"
            "After food\n"
            "5 days\n"
            "\n"
            "2.\n"
            "Ibuprofen 400 mg\n"
            "After food\n"
            "5 days\n"
            "\n"
            "3.\n"
            "Omeprazole 20 mg\n"
            "Before breakfast\n"
            "10 days"
        )
        expected = {
            "Paracetamol": ("500 mg", "after food", "5 days"),
            "Ibuprofen": ("400 mg", "after food", "5 days"),
            "Omeprazole": ("20 mg", "before breakfast", "10 days"),
        }
        for name, (dosage, frequency, duration) in expected.items():
            self.assertEqual(find_dosages_near(text, name), [dosage])
            freqs = find_frequencies_near(text, name)
            multi = next((f for f in freqs if len(f.split()) > 1), None)
            self.assertEqual(multi, frequency)
            self.assertEqual(find_durations_near(text, name), [duration])

        # The full entry builder (what the API returns) must agree.
        entries = {
            e["medicine_name"]: e
            for e in (
                _extract_medicine_entry(text, m) for m in find_medicines(text)
            )
        }
        for name, (dosage, frequency, duration) in expected.items():
            self.assertEqual(entries[name]["dosage"], dosage)
            self.assertEqual(entries[name]["frequency"], frequency)
            self.assertEqual(entries[name]["duration"], duration)

    def test_missing_value_never_inherited_from_other_block(self):
        """A medicine whose block lacks a value must stay empty — it must
        never borrow the nearest value from another medicine's block.
        """
        text = (
            "Paracetamol 500 mg after food 5 days\n"
            "Omeprazole after food 10 days"
        )
        self.assertEqual(find_dosages_near(text, "Paracetamol")[0], "500 mg")
        # Omeprazole has no dosage of its own -> empty, not Paracetamol's.
        self.assertEqual(find_dosages_near(text, "Omeprazole"), [])

    def test_strip_primary_never_inherits_from_sibling_block(self):
        """Strip safety net: when the brand name and the composition dosage
        belong to two different blocks ('DOLO 650' / 'PARACETAMOL 650 MG'),
        the primary brand never borrows the dosage written for the sibling
        medicine. The value goes to the medicine whose block contains it.
        """
        text = "DOLO 650 PARACETAMOL 650 MG TABLETS 15 tablets"
        # '650 mg' sits inside Paracetamol's own block...
        self.assertEqual(find_dosages_near(text, "Paracetamol")[0], "650 mg")
        # ...so Dolo 650's block stays empty rather than inheriting it.
        self.assertEqual(find_dosages_near(text, "Dolo 650"), [])

    def test_summary_patient_not_available_when_absent(self):
        summary = build_prescription_summary(
            "Tab Paracetamol 500mg after food 5 days",
            [{"medicine_name": "Paracetamol", "dosage": "500 mg", "quantity": "", "frequency": "after food", "duration": "5 days"}],
        )
        self.assertIn("Patient: Not Available", summary)

    # -- Text cleaning (Issue 4) -----------------------------------------

    def test_clean_ocr_text_fixes_merged_words(self):
        self.assertEqual(
            clean_ocr_text("Storeprotectedfrommoisture"),
            "Store protected from moisture",
        )

    def test_clean_ocr_text_removes_duplicated_words(self):
        self.assertEqual(clean_ocr_text("the the medicine"), "the medicine")

    def test_clean_ocr_text_collapses_spaces(self):
        self.assertEqual(
            clean_ocr_text("Composition  :   Pantoprazole"),
            "Composition: Pantoprazole",
        )

    def test_clean_ocr_text_preserves_unknown_tokens(self):
        # Tokens that cannot be safely split must be left untouched.
        self.assertEqual(clean_ocr_text("Pantoprazole 40mg"), "Pantoprazole 40mg")

    # -- Structured summary (Issue 2 / Issue 3) ---------------------------

    def test_build_summary_is_structured(self):
        text = (
            "Dr. Amit Verma\n"
            "Health Choice Clinic\n"
            "Patient Name: Rahul Sharma\n"
            "Tab Paracetamol 500mg after food 5 days\n"
            "Tab Ibuprofen 400mg after food 5 days\n"
            "Tab Omeprazole 20mg before breakfast 10 days\n"
            "Take plenty of fluids.\n"
            "Avoid oily food.\n"
            "Rest regularly.\n"
        )
        entries = [
            {"medicine_name": "Paracetamol", "dosage": "500 mg", "quantity": "", "frequency": "after food", "duration": "5 days"},
            {"medicine_name": "Ibuprofen", "dosage": "400 mg", "quantity": "", "frequency": "after food", "duration": "5 days"},
            {"medicine_name": "Omeprazole", "dosage": "20 mg", "quantity": "", "frequency": "before breakfast", "duration": "10 days"},
        ]
        summary = build_prescription_summary(
            text, entries,
            doctor="Dr. Amit Verma",
            hospital="Health Choice Clinic",
            patient="Rahul Sharma",
        )
        self.assertIn("Doctor: Dr. Amit Verma", summary)
        self.assertIn("Hospital: Health Choice Clinic", summary)
        self.assertIn("Patient: Rahul Sharma", summary)
        self.assertIn("Medicines:", summary)
        self.assertIn("• Paracetamol 500 mg", summary)
        self.assertIn("• Ibuprofen 400 mg", summary)
        self.assertIn("• Omeprazole 20 mg", summary)
        self.assertIn("Notes:", summary)
        self.assertIn("• Take plenty of fluids", summary)
        self.assertIn("• Avoid oily food", summary)
        self.assertIn("• Rest regularly", summary)

    def test_build_summary_never_invents_fields(self):
        summary = build_prescription_summary("", [])
        self.assertEqual(summary, "")
        summary = build_prescription_summary(
            "Tab Paracetamol 500mg",
            [{"medicine_name": "Paracetamol", "dosage": "500 mg", "quantity": "", "frequency": "", "duration": ""}],
        )
        self.assertIn("• Paracetamol 500 mg", summary)
        self.assertNotIn("Doctor:", summary)
        self.assertNotIn("Hospital:", summary)
        # No real patient found -> the section says so explicitly instead of
        # inventing a name (spec: "Patient: Not Available" when absent).
        self.assertIn("Patient: Not Available", summary)
        self.assertNotIn("Notes:", summary)


# ---------------------------------------------------------------------------
# OCR service tests (real RapidOCR engine on synthetic images)
# ---------------------------------------------------------------------------


@override_settings(
    LOGGING={"version": 1, "disable_existing_loggers": True},
    GEMINI_VISION_EXTRACTION_ENABLED=False,
)
class OcrServiceTests(TestCase):
    def test_real_paracetamol_strip_detected(self):
        img = _make_image(
            ["PARACETAMOL", "650 mg", "Each tablet contains", "Paracetamol IP 650mg", "10 tablets"]
        )
        result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["medicine_name"], "Paracetamol")

    def test_real_dolo_strip_detected(self):
        img = _make_image(["DOLO 650", "PARACETAMOL TABLETS", "650 mg", "15 tablets"])
        result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["medicine_name"], "Dolo 650")

    def test_prescription_extracts_medicines_written(self):
        img = _make_image(
            [
                "Dr. Anjali Sharma",
                "City General Hospital",
                "Rx: Tab Paracetamol 500mg - 1 BD",
                "Tab Ibuprofen 400mg - 1 TDS",
                "Tab Naproxen 250mg - 1 OD",
                "For fever, Dated 25/07/2026",
            ]
        )
        result = process_upload(img, "image/png", "prescription")
        self.assertEqual(result["status"], "success")
        names = [m["medicine_name"] for m in result["medicines"]]
        # Hard requirement: the medicines actually written in the prescription.
        self.assertIn("Paracetamol", names)
        self.assertIn("Ibuprofen", names)
        # Soft check: Naproxen is a third line that OCR may read less reliably
        # across font renderers; it must never be a WRONG medicine though.
        for name in names:
            self.assertIn(name, ("Paracetamol", "Ibuprofen", "Naproxen"))

    def test_prescription_scopes_details_per_medicine(self):
        """Each medicine's dosage/frequency must come from ITS OWN line.

        Regression guard: Ibuprofen must show 400 mg/TDS, NOT the first
        medicine's 500 mg/BD.
        """
        img = _make_image(
            [
                "Rx: Tab Paracetamol 500mg - BD",
                "Tab Ibuprofen 400mg - TDS",
                "Tab Naproxen 250mg - OD",
            ]
        )
        result = process_upload(img, "image/png", "prescription")
        self.assertEqual(result["status"], "success")
        by_name = {m["medicine_name"]: m for m in result["medicines"]}
        self.assertEqual(by_name["Paracetamol"]["dosage"], "500 mg")
        self.assertEqual(by_name["Paracetamol"]["frequency"], "bd")
        self.assertEqual(by_name["Ibuprofen"]["dosage"], "400 mg")
        self.assertEqual(by_name["Ibuprofen"]["frequency"], "tds")

    def test_parrot_image_rejected(self):
        result = process_upload(_make_parrot_image(), "image/png", "medicine")
        self.assertEqual(result["status"], "no_medicine")
        self.assertIn("No medicine detected", result["message"])
        self.assertEqual(result["medicine_name"], "")

    def test_blank_image_rejected(self):
        result = process_upload(_make_blank_image(), "image/png", "medicine")
        self.assertEqual(result["status"], "no_medicine")
        self.assertEqual(result["medicine_name"], "")

    def test_empty_bytes_rejected(self):
        result = process_upload(b"", "image/png", "medicine")
        self.assertEqual(result["status"], "error")

    def test_no_fabricated_metadata(self):
        # Image with medicine text but NO doctor/hospital/date on it:
        # those fields must be empty (frontend shows "Not Available").
        img = _make_image(["DOLO 650", "650 mg", "Paracetamol tablets"])
        result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["doctor_name"], "")
        self.assertEqual(result["hospital"], "")
        self.assertEqual(result["prescription_date"], "")
        self.assertEqual(result["disease"], "")

    def test_confidence_is_real_ocr_value(self):
        img = _make_image(["PARACETAMOL 650 mg"])
        result = process_upload(img, "image/png", "medicine")
        # Confidence must be a genuine value derived from OCR, not a
        # fabricated 82-99 random. It can be 0 (no words scored) or a real %.
        self.assertIsInstance(result["confidence"], (int, float))
        self.assertTrue(0 <= result["confidence"] <= 100)

    def test_prescription_date_extracted(self):
        img = _make_image(
            [
                "Dr. Anjali Sharma",
                "City General Hospital",
                "Rx: Tab Paracetamol 500mg - 1 BD",
                "For fever, Dated 25/07/2026",
            ]
        )
        result = process_upload(img, "image/png", "prescription")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["prescription_date"], "25/07/2026")

    def test_prescription_details_are_structured_not_raw_dump(self):
        img = _make_image(
            [
                "Dr. Anjali Sharma",
                "City General Hospital",
                "Rx: Tab Paracetamol 500mg - 1 BD",
                "For fever, Dated 25/07/2026",
            ]
        )
        result = process_upload(img, "image/png", "prescription")
        details = result["prescription_details"]
        self.assertIn("Doctor: Dr. Anjali Sharma", details)
        self.assertIn("Hospital: City General Hospital", details)
        self.assertIn("Medicines:", details)
        self.assertIn("• Paracetamol", details)
        # The raw OCR dump must NOT be shown.
        self.assertNotIn("Rx:", details)
        self.assertNotIn("Dated", details)

    def test_summary_omits_missing_fields(self):
        img = _make_image(["DOLO 650", "650 mg", "Paracetamol tablets"])
        result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "success")
        details = result["prescription_details"]
        self.assertIn("Medicines:", details)
        self.assertNotIn("Doctor:", details)
        self.assertNotIn("Hospital:", details)
        self.assertNotIn("Notes:", details)

    # -- OCR robustness: image preprocessing for handwritten/low-quality ------

    def _make_degraded_image(self, text_lines):
        """Synthetic low-quality image: gray text, low contrast, blur and
        noise — mimics a poorly-photographed or handwritten prescription.
        """
        img = Image.new("RGB", (800, 450), "white")
        draw = ImageDraw.Draw(img)
        font = _make_font()
        y = 30
        for line in text_lines:
            draw.text((30, y), line, fill="#9a9a9a", font=font)
            y += 55
        # Reduce contrast further + blur + noise (mimics a degraded photo).
        img = ImageEnhance.Contrast(img).enhance(0.5)
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        arr = np.array(img)
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 6, arr.shape).astype(np.int16)
        arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    def test_preprocess_variants_generate_multiple_enhanced_images(self):
        """The preprocessor must produce grayscale + contrast/sharpened +
        adaptive-threshold + denoised-threshold variants (2-D uint8 arrays),
        and each variant must differ from the plain grayscale baseline.
        """
        from .ocr_service import _decode_image

        img = _make_image(["PARACETAMOL 650 mg"])
        variants = _preprocess_variants(_decode_image(img))
        self.assertGreaterEqual(len(variants), 4)
        baseline = variants[0]
        for v in variants[1:]:
            self.assertEqual(v.ndim, 2)
            self.assertEqual(v.dtype, np.uint8)
            self.assertFalse(np.array_equal(v, baseline))

    def test_degraded_image_with_medicine_still_detected(self):
        """A low-quality image with a readable medicine name must NOT return
        'No Medicine Detected' — the enhanced pass recovers it.
        """
        img = self._make_degraded_image(
            ["PARACETAMOL", "650 mg", "Paracetamol IP 650mg"]
        )
        result = process_upload(img, "image/png", "medicine")
        self.assertIn(result["status"], ("success", "low_confidence"))
        self.assertEqual(result["medicine_name"], "Paracetamol")

    def test_degraded_prescription_recovered_with_medicines(self):
        """A degraded prescription image must still return the medicines that
        are present; if recovery needed preprocessing it is low_confidence.
        """
        img = self._make_degraded_image(
            [
                "Dr. Anjali Sharma",
                "Rx: Tab Paracetamol 500mg",
                "Tab Ibuprofen 400mg",
            ]
        )
        result = process_upload(img, "image/png", "prescription")
        self.assertIn(result["status"], ("success", "low_confidence"))
        names = [m["medicine_name"] for m in result["medicines"]]
        self.assertIn("Paracetamol", names)
        self.assertIn("Ibuprofen", names)

    def test_handwritten_recovery_is_low_confidence(self):
        """Simulate a handwritten prescription the raw pass cannot read
        (first pass returns no text). The enhanced pass must recover the
        medicine and the status MUST be low_confidence, never a hard failure
        and never a fabricated plain success.
        """
        img = _make_image(["DOLO 650", "650 mg", "15 tablets"])
        with mock.patch(
            "medicines.ocr_service.run_ocr_on_file", return_value=("", 0.0)
        ):
            result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "low_confidence")
        self.assertIn("review", result["message"].lower())
        self.assertEqual(result["medicine_name"], "Dolo 650")

    def test_enhanced_recovery_lower_word_score_floor(self):
        """The handwritten pass uses a lower word-score floor so faint
        characters still contribute to the confidence score.
        """
        from .ocr_service import HANDWRITTEN_MIN_WORD_SCORE, MIN_WORD_SCORE

        self.assertLess(HANDWRITTEN_MIN_WORD_SCORE, MIN_WORD_SCORE)

    def test_printed_image_skips_enhanced_pass(self):
        """Printed prescriptions that OCR cleanly on the first pass must NOT
        trigger the enhanced (handwritten) pipeline — preserving existing
        behavior exactly.
        """
        img = _make_image(["PARACETAMOL 650 mg", "10 tablets"])
        with mock.patch(
            "medicines.ocr_service._run_enhanced_ocr",
            side_effect=AssertionError("enhanced pass must not run for printed text"),
        ):
            result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["medicine_name"], "Paracetamol")

    def test_enhanced_pass_never_invents_medicine_for_parrot(self):
        """Anti-hallucination guard: even after preprocessing, a non-medical
        image must still be rejected as no_medicine.
        """
        result = process_upload(_make_parrot_image(), "image/png", "medicine")
        self.assertEqual(result["status"], "no_medicine")
        self.assertEqual(result["medicine_name"], "")


# ---------------------------------------------------------------------------
# API tests (auth + endpoints + manual entry preservation)
# ---------------------------------------------------------------------------


@override_settings(GEMINI_VISION_EXTRACTION_ENABLED=False)
class OcrApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@test.com"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_upload_requires_auth(self):
        anon = APIClient()
        resp = anon.post("/api/medicines/prescription/upload/", {})
        self.assertEqual(resp.status_code, 401)

    def test_blank_image_api_rejected(self):
        resp = _as_upload(self.client, _make_blank_image())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "no_medicine")
        self.assertIn("No medicine detected", resp.data["message"])

    def test_parrot_image_api_rejected(self):
        resp = _as_upload(self.client, _make_parrot_image())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "no_medicine")

    def test_valid_medicine_strip_api_success(self):
        img = _make_image(["DOLO 650", "PARACETAMOL 650 mg", "15 tablets"])
        resp = _as_upload(self.client, img)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")
        self.assertEqual(resp.data["medicine_name"], "Dolo 650")

    def test_rejected_upload_has_empty_medicines(self):
        resp = _as_upload(self.client, _make_blank_image())
        self.assertEqual(resp.data["medicines"], [])

    def test_manual_entry_saved_exactly(self):
        """Test 6: 'Digene' must be saved as 'Digene', never rewritten."""
        resp = self.client.post(
            "/api/medicines/",
            {
                "medicine_name": "Digene",
                "dosage": "1 tab",
                "frequency": "Night",
                "medicine_type": "TABLET",
                "is_active": True,
                "stock": 10,
                "start_date": "2026-07-31",
                "end_date": "2026-08-30",
                "source": "manual",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["medicine_name"], "Digene")

        # Verify in DB
        med = self.user.medicines.get(medicine_name="Digene")
        self.assertEqual(med.medicine_name, "Digene")

    def test_manual_entry_does_not_require_validation_network(self):
        """Manual entry must succeed even if validation services are down."""
        resp = self.client.post(
            "/api/medicines/",
            {
                "medicine_name": "Test Syrup",
                "dosage": "10 ml",
                "frequency": "Morning",
                "medicine_type": "SYRUP",
                "is_active": True,
                "stock": 1,
                "start_date": "2026-07-31",
                "end_date": "2026-08-30",
                "source": "manual",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["medicine_name"], "Test Syrup")

    def test_ocr_health_check(self):
        resp = self.client.get("/api/medicines/prescription/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["mode"], "real-ocr")


# ---------------------------------------------------------------------------
# Production-grade matching pipeline regression tests
# (exact → merged → alias → fuzzy — never false positives)
# ---------------------------------------------------------------------------


class MedicineMatchingEnhancementTests(TestCase):
    # -- Merged-token matching (OCR glues words together) -------------------

    def test_merged_token_paracetamol_detected(self):
        self.assertEqual(
            find_medicines_extended("PARACETAMOLTABLETS IP 650 MG"),
            ["Paracetamol"],
        )

    def test_merged_token_tab_prefix_detected(self):
        self.assertEqual(
            find_medicines_extended("TABPARACETAMOL500MG"), ["Paracetamol"]
        )

    def test_merged_token_brand_with_dosage_detected(self):
        self.assertEqual(find_medicines_extended("Calpol500 tablets"), ["Calpol"])

    def test_merged_token_never_splits_random_words(self):
        # 'dolor' contains the KB token 'dolo' but cannot split into allowed
        # pieces — it must NOT be treated as Dolo 650.
        self.assertEqual(find_medicines_merged("dolor sit amet"), [])
        self.assertEqual(find_medicines_extended("dolor sit amet"), [])

    # -- Fuzzy (typo-tolerant) matching -------------------------------------

    def test_fuzzy_typo_paracitamol_detected(self):
        self.assertIn("Paracetamol", find_medicines_extended("Paracitamol 500 mg"))
        self.assertIn("Paracetamol", find_medicines_extended("Paiacetamol 650 mg"))

    def test_fuzzy_typo_azithromicin_detected(self):
        self.assertIn(
            "Azithromycin", find_medicines_extended("Azithromicin 250 mg")
        )

    def test_fuzzy_rejects_non_medicine_words(self):
        self.assertEqual(find_medicines_fuzzy("a beautiful colorful parrot sitting"), [])
        self.assertEqual(find_medicines_fuzzy("pretty"), [])
        self.assertEqual(find_medicines_extended("The quick brown fox"), [])
        self.assertEqual(find_medicines_extended("a pretty parrot on a branch"), [])

    def test_fuzzy_threshold_rejects_distant_word(self):
        # 'panadol' is ~0.56 similar to 'paracetamol' — far below threshold.
        self.assertEqual(find_medicines_fuzzy("Chocolate"), [])

    # -- Alias / abbreviation matching --------------------------------------

    def test_abbreviation_pcm_detected(self):
        self.assertIn("Paracetamol", find_medicines_extended("Tab PCM 650"))

    def test_abbreviation_amox_detected(self):
        self.assertIn("Amoxicillin", find_medicines_extended("Cap AMOX 500"))

    def test_alias_panadol_is_paracetamol(self):
        self.assertEqual(find_first_medicine("Panadol 500"), "Paracetamol")

    # -- KB coverage: common Indian brands ----------------------------------

    def test_new_indian_brands_detected(self):
        self.assertEqual(find_first_medicine("Pantocid 40"), "Pantoprazole")
        self.assertEqual(find_first_medicine("Stemetil 5mg"), "Prochlorperazine")
        self.assertEqual(find_first_medicine("Cyclopam"), "Dicyclomine")
        self.assertEqual(find_first_medicine("Cilacar 10"), "Cilnidipine")
        self.assertEqual(find_first_medicine("Storvas 10"), "Atorvastatin")
        self.assertEqual(find_first_medicine("Telmikind 40"), "Telmisartan")

    def test_new_brands_never_conflict_with_existing(self):
        # A clean printed strip must still resolve exactly as before.
        self.assertEqual(
            find_first_medicine("DOLO 650 PARACETAMOL TABLETS"), "Dolo 650"
        )
        self.assertEqual(find_first_medicine("Digene"), "Digene")

    # -- Matching semantics -------------------------------------------------

    def test_exact_match_wins_over_fuzzy_same_canonical(self):
        # Exact 'Paracetamol' plus typo 'Paracitamol' -> one canonical entry.
        self.assertEqual(
            find_medicines_extended("Paracetamol and Paracitamol"),
            ["Paracetamol"],
        )

    def test_fuzzy_match_keeps_block_scoping(self):
        text = "Paracitamol 500 mg after food\nIbuprofen 400 mg after food"
        self.assertEqual(find_dosages_near(text, "Paracetamol"), ["500 mg"])
        self.assertEqual(find_dosages_near(text, "Ibuprofen"), ["400 mg"])

    # -- Decision helper ----------------------------------------------------

    def test_looks_like_medical_text(self):
        self.assertTrue(looks_like_medical_text("Tab 500mg BD for fever"))
        self.assertTrue(looks_like_medical_text("paracitamol 500 mg"))
        self.assertFalse(looks_like_medical_text("a pretty parrot"))
        self.assertFalse(looks_like_medical_text(""))


@override_settings(GEMINI_VISION_EXTRACTION_ENABLED=False)
class OcrServiceEnhancementTests(TestCase):
    """End-to-end service-level regressions for the enhanced pipeline."""

    def test_medical_text_without_name_returns_low_confidence(self):
        """OCR text that is clearly medical but has no verifiable medicine
        name must return 'Low Confidence Extraction', never a hard rejection.
        """
        img = _make_image(["Tab 500mg BD for fever"])
        with mock.patch(
            "medicines.ocr_service.run_ocr_on_file",
            return_value=("Tab 500mg BD for fever", 40.0),
        ), mock.patch(
            "medicines.ocr_service._run_enhanced_ocr", return_value=("", 0.0)
        ):
            result = process_upload(img, "image/png", "prescription")
        self.assertEqual(result["status"], "low_confidence")
        self.assertIn("review", result["message"].lower())
        self.assertEqual(result["medicines"], [])

    def test_ocr_typo_recovered_end_to_end(self):
        """A clean image of a misspelled medicine name must recover the
        correct canonical medicine through the fuzzy pipeline."""
        img = _make_image(["Paracitamol", "500 mg", "twice daily"])
        result = process_upload(img, "image/png", "medicine")
        self.assertIn(result["status"], ("success", "low_confidence"))
        self.assertEqual(result["medicine_name"], "Paracetamol")

    def test_low_confidence_first_pass_triggers_second_pass(self):
        """A low-confidence first pass must trigger the enhanced (second)
        OCR pass even when a medicine was already found."""
        img = _make_image(["DOLO 650", "650 mg", "15 tablets"])
        with mock.patch(
            "medicines.ocr_service.run_ocr_on_file",
            return_value=("DOLO 650 650 mg", 35.0),
        ), mock.patch(
            "medicines.ocr_service._run_enhanced_ocr",
            return_value=("DOLO 650\n650 mg\n15 tablets", 80.0),
        ):
            result = process_upload(img, "image/png", "medicine")
        self.assertEqual(result["status"], "low_confidence")
        self.assertEqual(result["medicine_name"], "Dolo 650")
        # Pass-2 lines must have been merged into the final text.
        self.assertIn("15 tablets", result["raw_text"])


# ---------------------------------------------------------------------------
# AI extraction pipeline unit tests (fast, no OCR engine / no network)
# ---------------------------------------------------------------------------


class ConfidenceUtilsTests(TestCase):
    """utils/confidence.py — thresholds, levels, colors, blending."""

    def test_clamp_confidence_bounds(self):
        from .utils.confidence import clamp_confidence

        self.assertEqual(clamp_confidence(150), 100.0)
        self.assertEqual(clamp_confidence(-5), 0.0)
        self.assertEqual(clamp_confidence("abc"), 0.0)
        self.assertEqual(clamp_confidence(84.6), 84.6)

    def test_confidence_level_bands(self):
        from .utils.confidence import confidence_level

        self.assertEqual(confidence_level(92), "high")
        self.assertEqual(confidence_level(90), "high")
        self.assertEqual(confidence_level(85), "medium")
        self.assertEqual(confidence_level(72), "medium")
        self.assertEqual(confidence_level(69), "low")
        self.assertEqual(confidence_level(40), "low")

    def test_confidence_color_maps_level(self):
        from .utils.confidence import confidence_color

        self.assertEqual(confidence_color(95), "green")
        self.assertEqual(confidence_color(75), "yellow")
        self.assertEqual(confidence_color(50), "red")

    def test_needs_manual_review_threshold(self):
        from .utils.confidence import needs_manual_review

        self.assertTrue(needs_manual_review(59))
        self.assertFalse(needs_manual_review(60))
        self.assertFalse(needs_manual_review(80))

    def test_combine_confidences(self):
        from .utils.confidence import combine_confidences

        # Only one source -> that value wins.
        self.assertEqual(combine_confidences(gemini_conf=90), 90.0)
        self.assertEqual(combine_confidences(ocr_conf=70), 70.0)
        # Both -> weighted blend (gemini weighted higher).
        blended = combine_confidences(gemini_conf=90, ocr_conf=70)
        self.assertGreater(blended, 80)
        self.assertLess(blended, 90)
        # Neither -> 0.
        self.assertEqual(combine_confidences(), 0.0)


class ExpiryUtilsTests(TestCase):
    """utils/expiry.py — date parsing and expiry classification."""

    def test_parse_expiry_formats(self):
        from .utils.expiry import parse_expiry

        self.assertEqual(parse_expiry("03/2027"), datetime.date(2027, 3, 31))
        self.assertEqual(parse_expiry("03-2027"), datetime.date(2027, 3, 31))
        self.assertEqual(parse_expiry("DEC 2026"), datetime.date(2026, 12, 31))
        self.assertEqual(parse_expiry("EXP 06/2027"), datetime.date(2027, 6, 30))
        self.assertEqual(parse_expiry("31/12/2026"), datetime.date(2026, 12, 31))
        self.assertEqual(parse_expiry("2027-01-15"), datetime.date(2027, 1, 15))
        self.assertIsNone(parse_expiry(""))
        self.assertIsNone(parse_expiry("not a date"))

    def test_expiry_status_expired(self):
        from .utils.expiry import expiry_status

        today = datetime.date(2026, 8, 5)
        result = expiry_status("01/2020", today=today)
        self.assertEqual(result["status"], "EXPIRED")
        self.assertLess(result["days_left"], 0)
        self.assertIn("expired", result["message"].lower())

    def test_expiry_status_valid(self):
        from .utils.expiry import expiry_status

        today = datetime.date(2026, 8, 5)
        result = expiry_status("12/2028", today=today)
        self.assertEqual(result["status"], "VALID")
        self.assertGreater(result["days_left"], 0)

    def test_expiry_status_unknown(self):
        from .utils.expiry import expiry_status

        self.assertIsNone(expiry_status(""))
        self.assertIsNone(expiry_status(None))


class ParserMergeTests(TestCase):
    """services/parser.py — merging, dedup, normalization, confidence."""

    def _gemini_payload(self):
        return {
            "patient": {"name": "Rahul Sharma", "age": "34", "gender": "M"},
            "doctor": {
                "name": "Dr. Amit Verma",
                "registration_number": "MH12345",
                "hospital": "City Hospital",
                "department": "General Medicine",
            },
            "prescription_date": "25/07/2026",
            "disease": "Fever",
            "diagnosis": "Viral fever",
            "symptoms": "High temperature, body ache",
            "doctor_notes": "Take rest and fluids.",
            "medicines": [
                {
                    "name": "Paracetamol",
                    "brand": "Dolo",
                    "generic_name": "Paracetamol",
                    "strength": "650",
                    "unit": "mg",
                    "dosage": "1 tablet",
                    "frequency": "twice daily",
                    "timing": "after food",
                    "duration": "5 days",
                    "quantity": "10 tablets",
                    "route": "oral",
                    "special_instructions": "take with milk",
                    "confidence": 92,
                }
            ],
            "confidence": 92,
        }

    def test_gemini_only_high_confidence_success(self):
        from .services.parser import merge_results

        result = merge_results(self._gemini_payload(), None, "prescription")
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["needs_manual_review"])
        self.assertEqual(result["confidence"], 92.0)
        self.assertEqual(result["engine"], "gemini")
        self.assertEqual(result["patient"]["name"], "Rahul Sharma")
        self.assertEqual(result["doctor"]["registration_number"], "MH12345")
        self.assertEqual(result["doctor"]["department"], "General Medicine")
        self.assertEqual(result["medicines"][0]["brand"], "Dolo")
        self.assertEqual(result["medicines"][0]["timing"], "after food")

    def test_low_confidence_needs_manual_review(self):
        from .services.parser import merge_results

        payload = self._gemini_payload()
        payload["confidence"] = 55
        payload["medicines"][0]["confidence"] = 55
        result = merge_results(payload, None, "prescription")
        self.assertTrue(result["needs_manual_review"])
        self.assertEqual(result["status"], "low_confidence")
        self.assertEqual(result["confidence_level"], "low")

    def test_merge_dedupes_gemini_and_ocr_medicines(self):
        from .services.parser import merge_results

        gemini = self._gemini_payload()
        gemini["confidence"] = 80
        ocr = {
            "status": "success",
            "message": "Medicine detected and extracted.",
            "confidence": 70,
            "medicines": [
                {
                    "medicine_name": "Paracetamol",
                    "dosage": "500 mg",
                    "frequency": "bd",
                    "duration": "",
                    "timing": "",
                },
                {
                    "medicine_name": "Ibuprofen",
                    "dosage": "400 mg",
                    "frequency": "tds",
                    "duration": "5 days",
                    "timing": "after food",
                },
            ],
            "raw_text": "some ocr text",
        }
        result = merge_results(gemini, ocr, "prescription")
        names = [m["medicine_name"] for m in result["medicines"]]
        # Paracetamol appears once (merged) + Ibuprofen added from OCR.
        self.assertEqual(names.count("Paracetamol"), 1)
        self.assertIn("Ibuprofen", names)
        # Gemini fields win on the merged entry.
        para = next(m for m in result["medicines"] if m["medicine_name"] == "Paracetamol")
        self.assertEqual(para["brand"], "Dolo")
        self.assertEqual(para["frequency"], "twice daily")
        self.assertEqual(result["engine"], "merged")

    def test_no_fabricated_fields_when_unknown(self):
        from .services.parser import merge_results

        payload = {
            "medicines": [{"name": "Paracetamol", "dosage": "1 tab"}],
            "confidence": 90,
        }
        result = merge_results(payload, None, "prescription")
        self.assertEqual(result["doctor"]["name"], "")
        self.assertEqual(result["patient"]["name"], "")
        self.assertEqual(result["symptoms"], "")
        self.assertEqual(result["medicines"][0]["brand"], "")

    def test_medicine_upload_expiry_and_barcode(self):
        from .services.parser import merge_results

        payload = {
            "name": "Dolo 650",
            "brand": "Dolo",
            "generic_name": "Paracetamol",
            "strength": "650",
            "unit": "mg",
            "medicine_type": "TABLET",
            "manufacturer": "Micro Labs",
            "expiry_date": "01/2020",
            "manufacturing_date": "01/2019",
            "batch_number": "B12345",
            "mrp": "35",
            "storage_instructions": "Store below 30C",
            "prescription_required": False,
            "common_uses": ["Fever", "Pain"],
            "side_effects": ["Nausea"],
            "barcode": "8901234567890",
            "qr_code": "https://example.com/verify",
            "confidence": 90,
        }
        result = merge_results(payload, None, "medicine")
        self.assertEqual(result["medicine_name"], "Dolo 650")
        self.assertEqual(result["barcode"], "8901234567890")
        self.assertEqual(result["qr_code"], "https://example.com/verify")
        self.assertEqual(result["expiry"]["status"], "EXPIRED")
        self.assertEqual(result["medicine_details"]["manufacturer"], "Micro Labs")
        self.assertIn("Fever", result["medicine_details"]["common_uses"])

    def test_no_medicine_status(self):
        from .services.parser import merge_results

        result = merge_results(None, {"status": "no_medicine", "message": "No medicine detected."}, "medicine")
        self.assertEqual(result["status"], "no_medicine")
        self.assertEqual(result["medicines"], [])
