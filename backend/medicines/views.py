import logging
import re
from datetime import timedelta, date

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Medicine
from .serializers import MedicineSerializer
from .ai_validator import get_validation_service

logger = logging.getLogger(__name__)

# ─── Refill email deduplication cache ───────────────────────────────
# Keys: (user_id, medicine_id) → date object of last sent email.
# Prevents duplicate refill emails across repeated page loads within
# the same server process. Resets on server restart (at most one
# extra email per restart, which is acceptable).
_refill_email_sent: dict[tuple[int, int], date] = {}


def _normalize(value: str) -> str:
    """Strip leading/trailing whitespace and collapse internal whitespace.

    "  150   mg " -> "150 mg"
    "Morning  "   -> "Morning"
    "  ACILOC "   -> "ACILOC"
    """
    return re.sub(r"\s+", " ", value.strip())


class MedicineViewSet(viewsets.ModelViewSet):

    serializer_class = MedicineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Medicine.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Override create to validate the medicine name using the
        validation pipeline before persisting the record.

        Pipeline:
            1. Normalize input
            2. AI Assistance (optional - typo correction)
            3. Drug Database Validation (authoritative - RxNorm, OpenFDA)
            4. Duplicate Check
            5. Save

        AI is OPTIONAL and NEVER blocks medicine creation.
        Drug databases are the PRIMARY authority.

        Manual entry (source="manual") is the exception:
            Manual input ALWAYS has the highest priority. The medicine name,
            dosage and frequency are saved EXACTLY as the user entered them.
            No AI correction, no normalization, no replacement.
        """
        medicine_name = request.data.get("medicine_name", "")

        # -- MANUAL ENTRY: save exactly what the user entered ---------------
        # Never auto-correct, never replace, never normalize. This is a
        # deliberate bypass of the validation pipeline so that e.g. "Digene"
        # is never rewritten to "Pinus digenea leaf oil".
        #
        # NOTE: `source=manual` is an intentional, auth-gated escape hatch
        # (only reachable by authenticated users). It intentionally skips the
        # AI / drug-database validation pipeline because manual input always
        # has highest priority. A lightweight EXACT-name duplicate check is
        # kept so accidental re-entries of the same name are still caught.
        source = request.data.get("source", "")
        if source == "manual":
            if not medicine_name or not str(medicine_name).strip():
                return Response(
                    {"success": False, "message": "Medicine name is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Duplicate check: same user + name + dosage + frequency
            # (mirrors the validated/OCR path so both flows are consistent).
            # The name itself is still saved EXACTLY as entered — only the
            # duplicate lookup uses a stripped comparison.
            duplicate_qs = Medicine.objects.filter(
                user=request.user,
                medicine_name__iexact=str(medicine_name).strip(),
                dosage__iexact=str(request.data.get("dosage", "")).strip(),
                frequency__iexact=str(request.data.get("frequency", "")).strip(),
            )
            if duplicate_qs.exists():
                return Response(
                    {
                        "success": False,
                        "message": "This medicine with the same dosage and schedule already exists.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(
                "Medicine SAVED (manual, exact): user=%s, medicine='%s', "
                "dosage='%s', frequency='%s'",
                request.user.username,
                medicine_name,
                request.data.get("dosage", ""),
                request.data.get("frequency", ""),
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers,
            )

        # -- OCR / validated flow -------------------------------------------
        if not medicine_name or not medicine_name.strip():
            return Response(
                {"success": False, "message": "Medicine name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -- Validate via pipeline (Normalize → AI → Drug DB) --
        service = get_validation_service()
        result = service.validate(medicine_name)

        # -- Genuine system-level error (very rare: all DB providers down) --
        if result.get("error"):
            error_msg = result["error"]
            logger.error(
                "Validation system failure for '%s': %s",
                medicine_name,
                error_msg,
            )
            return Response(
                {
                    "success": False,
                    "message": "Medicine validation service is temporarily unavailable. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # -- Validation decision --
        if not result.get("valid", False):
            message = result.get("message", "Invalid medicine name. Please enter a valid medicine.")
            logger.info(
                "Rejected '%s': %s (ai_assisted=%s, drug_db=%s)",
                medicine_name,
                message,
                result.get("ai_assisted", False),
                result.get("drug_db_exists", False),
            )
            return Response(
                {
                    "success": False,
                    "message": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -- Valid: save with the NORMALIZED name --
        # Normalize whitespace: strip + collapse internal spaces
        normalized_name = _normalize(result.get("normalized_name", medicine_name))
        dosage = _normalize(request.data.get("dosage", ""))
        frequency = _normalize(request.data.get("frequency", ""))

        # -- Duplicate prevention: same user + normalized name + dosage + frequency --
        duplicate_qs = Medicine.objects.filter(
            user=request.user,
            medicine_name__iexact=normalized_name,
            dosage__iexact=dosage,
            frequency__iexact=frequency,
        )

        logger.info(
            "Duplicate check: user=%s, medicine='%s' (normalized), "
            "dosage='%s', frequency='%s' -> %d existing records",
            request.user.username,
            normalized_name,
            dosage,
            frequency,
            duplicate_qs.count(),
        )

        if duplicate_qs.exists():
            logger.warning(
                "Duplicate REJECTED: user=%s, medicine='%s', "
                "dosage='%s', frequency='%s'",
                request.user.username,
                normalized_name,
                dosage,
                frequency,
            )
            return Response(
                {
                    "success": False,
                    "message": "This medicine with the same dosage and schedule already exists.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Medicine '%s' validated successfully -> saved as '%s' "
            "(confidence=%.2f, time=%.0fms)",
            medicine_name,
            normalized_name,
            result.get("confidence", 0.0),
            result.get("time_taken_ms", 0),
        )

        # Override data with normalized values (strips + collapses whitespace)
        # so the database stores clean values and duplicate checking stays consistent
        mutable_data = request.data.copy()
        mutable_data["medicine_name"] = normalized_name
        mutable_data["dosage"] = dosage
        mutable_data["frequency"] = frequency

        serializer = self.get_serializer(data=mutable_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        logger.info(
            "Medicine SAVED: user=%s, medicine='%s', dosage='%s', frequency='%s'",
            request.user.username,
            normalized_name,
            dosage,
            frequency,
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


def _parse_frequency_per_day(frequency_str):
    """
    Parse a frequency string like "Twice daily", "1", "3 times", "0.5"
    and return a numeric value representing doses per day.
    """
    if not frequency_str:
        return 1

    freq = frequency_str.lower().strip()

    # Direct numeric
    try:
        return float(freq)
    except ValueError:
        pass

    # Map common string patterns to numeric values
    frequency_map = {
        "once daily": 1,
        "once a day": 1,
        "one time": 1,
        "twice daily": 2,
        "twice a day": 2,
        "two times": 2,
        "three times": 3,
        "three times daily": 3,
        "three times a day": 3,
        "four times": 4,
        "four times daily": 4,
        "every 8 hours": 3,
        "every 12 hours": 2,
        "every 6 hours": 4,
        "once weekly": 1 / 7,
        "once a week": 1 / 7,
        "monthly": 1 / 30,
        "once monthly": 1 / 30,
    }

    if freq in frequency_map:
        return frequency_map[freq]

    # Try to extract number from strings like "3 times", "2x daily"
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', freq)
    if match:
        return float(match.group(1))

    return 1


def _parse_dosage(dosage_str):
    """
    Parse dosage string like "500mg", "10ml", "1 tablet" and return
    a numeric quantity per dose (default 1).
    """
    if not dosage_str:
        return 1

    dosage = dosage_str.lower().strip()

    # Extract numeric part
    match = re.search(r'(\d+(?:\.\d+)?)', dosage)
    if match:
        return float(match.group(1))

    return 1


def _calculate_refill_data(medicine, today=None):
    """
    Calculate refill data for a single medicine based on its fields:
    - stock: current quantity remaining
    - frequency: how many times per day
    - dosage: quantity per dose
    - start_date / end_date: tracking period

    Returns a dict with all refill calculation fields.
    """
    if today is None:
        today = date.today()

    stock = medicine.stock if medicine.stock is not None else 0
    # Use the explicit frequency_doses_per_day field when available,
    # falling back to string-parsing for legacy records.
    doses_per_day = getattr(medicine, 'frequency_doses_per_day', None) or _parse_frequency_per_day(medicine.frequency)
    quantity_per_dose = _parse_dosage(medicine.dosage)
    daily_consumption = doses_per_day * quantity_per_dose

    # Calculate days remaining
    if daily_consumption > 0:
        days_remaining = stock / daily_consumption
    else:
        days_remaining = 0

    depletion_days = int(days_remaining)
    depletion_date = today + timedelta(days=depletion_days)

    # Determine refill status
    if days_remaining <= 2:
        refill_status = "URGENT"
        refill_priority = 3
    elif days_remaining <= 7:
        refill_status = "REFILL_SOON"
        refill_priority = 2
    else:
        refill_status = "NO_REFILL_NEEDED"
        refill_priority = 1

    return {
        "id": medicine.id,
        "medicine_name": medicine.medicine_name,
        "medicine_type": medicine.medicine_type,
        "dosage": medicine.dosage,
        "frequency": medicine.frequency,
        "current_stock": stock,
        "daily_consumption": daily_consumption,
        "doses_per_day": doses_per_day,
        "quantity_per_dose": quantity_per_dose,
        "days_remaining": round(days_remaining, 1),
        "depletion_days": depletion_days,
        "depletion_date": depletion_date.isoformat(),
        "start_date": medicine.start_date.isoformat() if medicine.start_date else None,
        "end_date": medicine.end_date.isoformat() if medicine.end_date else None,
        "is_active": medicine.is_active,
        "refill_status": refill_status,
        "refill_priority": refill_priority,
        "instructions": medicine.instructions or "",
    }


def _send_refill_email(user, medicine_data):
    """
    Send a refill alert email to the user for a specific medicine.
    Prevents duplicate emails using an in-memory cache keyed by
    (user_id, medicine_id, today).  At most one email per medicine
    per calendar day per server process.
    """
    today = timezone.now().date()
    cache_key = (user.id, medicine_data["id"])

    if _refill_email_sent.get(cache_key) == today:
        logger.info(
            "Refill email already sent today for %s to %s. Skipping.",
            medicine_data["medicine_name"],
            user.email,
        )
        return False

    # Check SMTP configuration
    email_host = getattr(settings, "EMAIL_HOST", None)
    email_user = getattr(settings, "EMAIL_HOST_USER", None)
    email_password = getattr(settings, "EMAIL_HOST_PASSWORD", None)

    if not all([email_host, email_user, email_password]):
        logger.warning(f"SMTP not configured. Cannot send refill email for {medicine_data['medicine_name']}.")
        return False

    # Send the refill email
    subject = f"PillSync Refill Alert: {medicine_data['medicine_name']}"
    message = (
        f"Your {medicine_data['medicine_name']} is expected to run out in approximately {medicine_data['depletion_days']} day(s).\n\n"
        f"Please arrange a refill before your medicine runs out to avoid missing your scheduled doses.\n\n"
        f"Estimated depletion date: {medicine_data['depletion_date']}\n\n"
        f"This is an automated PillSync reminder."
    )
    html_message = (
        f"<div style='font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;'>"
        f"<div style='background: linear-gradient(135deg, #0F766E, #14B8A6); padding: 20px; border-radius: 12px 12px 0 0;'>"
        f"<h1 style='color: white; margin: 0; font-size: 24px;'>💊 PillSync Refill Alert</h1>"
        f"</div>"
        f"<div style='background: #f8fafc; padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;'>"
        f"<p style='color: #334155; font-size: 16px; margin-bottom: 16px;'>Dear {user.get_full_name() or user.username},</p>"
        f"<p style='color: #334155; font-size: 16px; line-height: 1.6;'>"
        f"Your <strong style='color: #0F766E;'>{medicine_data['medicine_name']}</strong> is expected to run out in approximately <strong style='color: #DC2626;'>{medicine_data['depletion_days']} day(s)</strong>."
        f"</p>"
        f"<p style='color: #334155; font-size: 16px; line-height: 1.6;'>"
        f"Please arrange a refill before your medicine runs out to avoid missing your scheduled doses."
        f"</p>"
        f"<div style='background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 16px; margin: 20px 0;'>"
        f"<p style='color: #B91C1C; font-size: 14px; margin: 0;'><strong>Estimated depletion date:</strong> {medicine_data['depletion_date']}</p>"
        f"</div>"
        f"<p style='color: #64748B; font-size: 14px; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px;'>"
        f"This is an automated PillSync reminder." 
        f"</p>"
        f"</div>"
        f"</div>"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@pillsync.com")

    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        if sent == 1:
            _refill_email_sent[cache_key] = today
            logger.info("Refill email sent successfully for %s to %s", medicine_data['medicine_name'], user.email)
            return True
        else:
            logger.error("Refill email failed for %s. send_mail returned %s", medicine_data['medicine_name'], sent)
            return False

    except Exception as e:
        logger.exception("Refill email failed for %s to %s", medicine_data['medicine_name'], user.email)
        return False


class RefillView(APIView):
    """
    GET: Returns refill data for all medicines belonging to the authenticated user.
    
    Calculates estimated remaining stock, days remaining, and depletion date
    for each medicine. Sends refill alert emails when stock is critically low
    (2 days or less remaining).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        medicines = Medicine.objects.filter(user=request.user, is_active=True)
        today = date.today()

        refill_data = []
        for medicine in medicines:
            data = _calculate_refill_data(medicine, today)
            refill_data.append(data)

        # Send refill emails for critically low stock (2 days or less).
        # Includes stock == 0 (depletion_days == 0) so the user knows
        # their medicine has run out.
        for data in refill_data:
            if data["depletion_days"] <= 2:
                _send_refill_email(request.user, data)

        # Sort by refill priority (urgent first)
        refill_data.sort(key=lambda x: x["refill_priority"], reverse=True)

        # Separate into categories
        urgent = [d for d in refill_data if d["refill_status"] == "URGENT"]
        refill_soon = [d for d in refill_data if d["refill_status"] == "REFILL_SOON"]
        no_refill = [d for d in refill_data if d["refill_status"] == "NO_REFILL_NEEDED"]

        return Response({
            "medicines": refill_data,
            "summary": {
                "urgent_count": len(urgent),
                "refill_soon_count": len(refill_soon),
                "no_refill_count": len(no_refill),
                "total_medicines": len(refill_data),
            },
            "urgent": urgent,
            "refill_soon": refill_soon,
            "no_refill": no_refill,
        })