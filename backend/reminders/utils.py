"""
Utility functions for the reminder notification system.

Provides helpers for:
- Formatting notification messages (SMS, Email)
- Building HTML email templates
- Normalizing Indian mobile numbers to E.164 format
- Windows-safe logging (strip emoji for console output)
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

from django.utils import timezone

from .models import Reminder

logger = logging.getLogger(__name__)


def normalize_phone_number(phone: Optional[str]) -> Optional[str]:
    """
    Normalize an Indian mobile number to E.164 format (+91XXXXXXXXXX).

    Accepts:
        - Raw 10-digit:  "9876543210"
        - With +91:      "+919876543210"
        - With 0 prefix: "09876543210"
        - With spaces/dashes: "+91 98765 43210"

    Returns:
        Normalized number in E.164 format, e.g. "+919876543210",
        or None if the input is empty/invalid.
    """
    if not phone:
        return None

    original = phone
    # Strip all non-digit characters except leading +
    cleaned = re.sub(r"[^\d+]+", "", phone.strip())

    # If it already starts with +91, just remove any extra chars
    if cleaned.startswith("+91"):
        # Ensure exactly +91 followed by 10 digits
        digits = re.sub(r"\D", "", cleaned[3:])
        if len(digits) == 10 and digits[0] in "6789":
            normalized = f"+91{digits}"
            logger.info(
                f"normalize_phone_number: {original} -> {normalized} "
                f"(already had +91 prefix)"
            )
            return normalized

    # Strip leading 0 if present
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    # Strip +91 if present without the +
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]

    # Remove any remaining non-digit characters
    digits = re.sub(r"\D", "", cleaned)

    # Validate: must be exactly 10 digits starting with 6-9
    if len(digits) == 10 and digits[0] in "6789":
        normalized = f"+91{digits}"
        logger.info(
            f"normalize_phone_number: {original} -> {normalized}"
        )
        return normalized

    logger.warning(
        f"normalize_phone_number: FAILED to normalize {original}. "
        f"Cleaned digits={digits!r}. Must be 10 digits starting with 6-9. "
        f"Returning None so caller can handle appropriately."
    )
    return None


def safe_log_message(message: str) -> str:
    """
    Strip emoji and non-ASCII characters for Windows console logging.

    Windows terminals (cmd.exe, older PowerShell) cannot render
    Unicode emoji like \U0001f48a (💊), causing UnicodeEncodeError.

    This converts the message to ASCII, ignoring non-ASCII chars,
    so logger output never crashes the Windows console.

    The actual notification content (SMS, Email, Push) is NEVER modified
    — this is only for log message output.
    """
    return message.encode("ascii", "ignore").decode("ascii")


def format_sms_message(medicine_name: str, dosage: str, reminder_time: str) -> str:
    """
    Format an SMS message for a medicine reminder.

    Args:
        medicine_name: Name of the medicine (e.g., "Paracetamol")
        dosage: Dosage information (e.g., "650mg")
        reminder_time: Time string (e.g., "08:00 AM")

    Returns:
        Formatted SMS text
    """
    return (
        f"Medicine Reminder\n\n"
        f"Medicine:\n{medicine_name}\n\n"
        f"Dosage:\n{dosage}\n\n"
        f"Time:\n{reminder_time}"
    )


def build_email_text(
    patient_name: str,
    medicine_name: str,
    dosage: str,
    reminder_time: str,
    reminder_date: str,
) -> str:
    """
    Build a plain text email body for a medicine reminder.

    Args:
        patient_name: Name of the patient
        medicine_name: Name of the medicine
        dosage: Dosage information
        reminder_time: Time string (e.g., "08:00 AM")
        reminder_date: Date string (e.g., "2026-07-27")

    Returns:
        Plain text email body string
    """
    return (
        f"Hello {patient_name},\n\n"
        f"This is your medicine reminder.\n\n"
        f"Medicine:\n{medicine_name}\n\n"
        f"Dosage:\n{dosage}\n\n"
        f"Time:\n{reminder_time}\n\n"
        f"Date:\n{reminder_date}\n\n"
        f"Please take your medicine on time.\n\n"
        f"Stay Healthy \u2764\ufe0f\n\n"
        f"\u2014 PillSync Team"
    )


def build_html_email(
    patient_name: str,
    medicine_name: str,
    dosage: str,
    reminder_time: str,
    reminder_date: str,
    doctor_name: Optional[str] = None,
) -> str:
    """
    Build a beautiful HTML email for a medicine reminder.

    Args:
        patient_name: Name of the patient
        medicine_name: Name of the medicine
        dosage: Dosage information
        reminder_time: Time string
        reminder_date: Date string
        doctor_name: Optional doctor name

    Returns:
        Complete HTML string for the email body
    """
    doctor_html = (
        f"""
        <tr>
            <td style="padding: 8px 0; color: #555555; font-size: 15px; line-height: 1.6;">
                <strong style="color: #333333;">\U0001f468\u200d\u2695\ufe0f Prescribed by:</strong> Dr. {doctor_name}
            </td>
        </tr>
        """
        if doctor_name
        else ""
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f6f9; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #145f58 0%, #1a8a7d 100%); padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; letter-spacing: 1px;">
                                \U0001f48a PillSync - Medicine Reminder
                            </h1>
                            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.85); font-size: 14px;">
                                Intelligent Medicine Reminder
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 8px 0; color: #145f58; font-size: 22px;">
                                Hello, {patient_name}!
                            </h2>
                            <p style="margin: 0 0 24px 0; color: #666666; font-size: 15px; line-height: 1.6;">
                                This is your medicine reminder.
                            </p>

                            <!-- Reminder Card -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0faf8; border-radius: 12px; border-left: 4px solid #145f58; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 8px 0; color: #555555; font-size: 15px; line-height: 1.6;">
                                                    <strong style="color: #333333;">\U0001f3e5 Medicine:</strong> {medicine_name}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #555555; font-size: 15px; line-height: 1.6;">
                                                    <strong style="color: #333333;">\U0001f4a7 Dosage:</strong> {dosage}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #555555; font-size: 15px; line-height: 1.6;">
                                                    <strong style="color: #333333;">\u23f0 Reminder Time:</strong> {reminder_time}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #555555; font-size: 15px; line-height: 1.6;">
                                                    <strong style="color: #333333;">\U0001f4c5 Reminder Date:</strong> {reminder_date}
                                                </td>
                                            </tr>
                                            {doctor_html}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 8px 0; color: #333333; font-size: 14px; line-height: 1.6;">
                                \u2705 Please take your medicine on time.
                            </p>
                            <p style="margin: 0; color: #888888; font-size: 13px; line-height: 1.6;">
                                \U0001f49a Stay Healthy \u2764\ufe0f
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #e9ecef;">
                            <p style="margin: 0; color: #888888; font-size: 14px; line-height: 1.6;">
                                \u2014 PillSync Team
                            </p>
                            <p style="margin: 12px 0 0 0; color: #aaaaaa; font-size: 12px; line-height: 1.5;">
                                This is an automated reminder from PillSync. Please do not reply to this email.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
