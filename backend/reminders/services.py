"""
Notification services for the PillSync reminder system.

Provides separate service classes for each notification channel:
- EmailService: Sends HTML emails via Django send_mail()
- SMSService: Sends SMS via Twilio
- PushNotificationService: REAL Web Push via pywebpush (VAPID)
- NotificationService: Orchestrates all channels and logs results
"""

import json
import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags

from .models import NotificationLog, Reminder
from .utils import (
    build_email_text,
    build_html_email,
    format_sms_message,
)

logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    """Mask an email for safe logging: us***@gmail.com"""
    if not email or "@" not in email:
        return "<invalid>"
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def mask_phone(phone: str) -> str:
    """Mask a phone number for safe logging: +91*****8743"""
    if not phone:
        return "<none>"
    digits = phone.strip()
    return f"{digits[:3]}*****{digits[-4:]}" if len(digits) > 7 else "***"


def classify_email_error(exc: Exception) -> str:
    """
    Turn an SMTP exception into a short, SAFE diagnostic message.
    Never includes passwords or full server payloads.
    """
    name = type(exc).__name__
    code = getattr(exc, "smtp_code", None)
    msg = str(exc).split("\n")[0][:200]

    if "SMTPAuthenticationError" in name or (code == 535):
        # Surface Gmail's specific 5.7.x rejection reason (e.g. BadCredentials
        # = the app password VALUE is wrong/revoked, vs. not using an app
        # password at all). Never include the credential itself.
        if "BadCredentials" in msg:
            reason = (
                "Gmail sub-reason=BadCredentials: the app password VALUE is "
                "wrong, expired or revoked - generate a fresh 16-char Gmail "
                "App Password and update EMAIL_HOST_PASSWORD in backend/.env"
            )
        elif "Application-specific password" in msg or "app password" in msg.lower():
            reason = (
                "Gmail sub-reason=not-an-app-password: 2FA must be enabled "
                "and EMAIL_HOST_PASSWORD must be a 16-char Gmail App Password"
            )
        else:
            reason = "Gmail rejected credentials"
        return (
            f"SMTPAuthenticationError ({reason}). Check EMAIL_HOST_USER and "
            f"EMAIL_HOST_PASSWORD in backend/.env. [{code}]"
        )
    if "SMTPConnectError" in name or "Connection" in name or "timeout" in msg.lower():
        return f"SMTP connection failed: {name} - check network/EMAIL_HOST/EMAIL_PORT"
    if "SMTPSenderRefused" in name:
        return f"SMTPSenderRefused: DEFAULT_FROM_EMAIL must match EMAIL_HOST_USER for Gmail [{code}]"
    if "SMTPRecipientsRefused" in name:
        return f"SMTPRecipientsRefused: invalid recipient address [{code}]"
    if "SSLError" in name or "TLS" in name:
        return f"TLS/SSL error: {name} - check EMAIL_USE_TLS/EMAIL_USE_SSL settings"
    return f"{name}: {msg}"


# ==========================================================
# Helper
# ==========================================================

def normalize_phone_number(phone_number: str) -> str:
    """
    Convert phone number to Twilio E.164 format.

    Examples:
        9569878743      -> +919569878743
        +919569878743   -> +919569878743
    """

    if not phone_number:
        return phone_number

    phone_number = phone_number.strip().replace(" ", "").replace("-", "")

    if phone_number.startswith("+"):
        return phone_number

    if len(phone_number) == 10:
        return f"+91{phone_number}"

    return phone_number


# ==========================================================
# Email Service
# ==========================================================

class EmailService:
    """Handles sending email notifications via Django send_mail()."""

    @staticmethod
    def send(
        reminder_id: int,
        medicine_name: str,
        recipient_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> tuple[bool, str]:

        if not recipient_email:
            logger.warning(
                f"Reminder {reminder_id} ({medicine_name}): "
                f"No recipient email provided."
            )
            return False, "No recipient email"

        if text_content is None:
            text_content = strip_tags(html_content)

        from_email = getattr(
            settings,
            "DEFAULT_FROM_EMAIL",
            "noreply@pillsync.com",
        )

        try:

            logger.info(
                f"EMAIL REMINDER START | reminder_id={reminder_id} "
                f"| recipient={mask_email(recipient_email)} "
                f"| host={getattr(settings, 'EMAIL_HOST', '?')}:"
                f"{getattr(settings, 'EMAIL_PORT', '?')} "
                f"| tls={getattr(settings, 'EMAIL_USE_TLS', '?')}"
            )

            sent = send_mail(
                subject=subject,
                message=text_content,
                from_email=from_email,
                recipient_list=[recipient_email],
                html_message=html_content,
                fail_silently=False,
            )

            if sent == 1:
                logger.info(
                    f"EMAIL SENT SUCCESSFULLY | reminder_id={reminder_id} "
                    f"| recipient={mask_email(recipient_email)}"
                )
                return True, "OK"

            return False, f"send_mail returned {sent}"

        except Exception as e:

            safe_error = classify_email_error(e)
            logger.error(
                f"EMAIL REMINDER FAILED | reminder_id={reminder_id} "
                f"| recipient={mask_email(recipient_email)} "
                f"| error={safe_error}"
            )

            return False, safe_error


# ==========================================================
# SMS Service
# ==========================================================

class SMSService:
    """Handles sending SMS notifications via Twilio."""

    @staticmethod
    def send(phone_number: str, message: str) -> bool:

        if not phone_number:
            logger.warning("SMS skipped. Empty phone number.")
            return False

        phone_number = normalize_phone_number(phone_number)

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        twilio_from = getattr(settings, "TWILIO_PHONE_NUMBER", None)

        if not all([account_sid, auth_token, twilio_from]):
            logger.warning("Twilio SMS credentials missing.")
            return False

        try:

            from twilio.rest import Client

            logger.info("=" * 60)
            logger.info("Sending SMS")
            logger.info(f"From : {twilio_from}")
            logger.info(f"To   : {phone_number}")
            logger.info("=" * 60)

            client = Client(account_sid, auth_token)

            response = client.messages.create(
                body=message,
                from_=twilio_from,
                to=phone_number,
            )

            logger.info(
                f"SMS sent successfully. SID={response.sid}"
            )

            return True

        except Exception as e:

            logger.exception(
                f"SMS FAILED -> {phone_number}"
            )

            return False


# ==========================================================
# Push Notification Service (real Web Push via pywebpush)
# ==========================================================

class PushNotificationService:
    """
    Sends REAL Web Push notifications to a user's browser(s) using
    pywebpush (VAPID-authenticated pushes to the browser push service).

    Flow:
      reminder -> this service -> browser push service (FCM/Mozilla)
      -> user's service worker 'push' event -> notification displayed.
    """

    @staticmethod
    def send_to_subscription(subscription, title: str, body: str) -> tuple[bool, str]:
        """Push one message to one stored subscription. Returns (ok, msg)."""
        from pywebpush import webpush, WebPushException

        vapid_private = getattr(settings, "VAPID_PRIVATE_KEY", None)
        vapid_claim_email = getattr(settings, "VAPID_SUBJECT", None) or ""

        if not vapid_private or not vapid_claim_email.startswith("mailto:"):
            return False, "CONFIGURATION_ERROR: VAPID keys not configured"

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=vapid_private,
                vapid_claims={
                    "sub": vapid_claim_email,
                },
            )
            return True, "OK"

        except WebPushException as e:
            response = getattr(e, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in (404, 410):
                # Subscription expired/gone on the push service side.
                return False, f"GONE:{status_code}"
            detail = ""
            if response is not None:
                try:
                    detail = f" | body={response.text[:200]}"
                except Exception:
                    detail = ""
            return False, f"WebPush error {status_code or 'N/A'}{detail}"

        except Exception as e:
            return False, str(e)

    @staticmethod
    def send_to_user(
        user_id: int,
        title: str,
        body: str,
        reminder_id: Optional[int] = None,
    ) -> tuple[int, int, bool, bool]:
        """
        Push to every subscription of a user.

        Returns (sent_count, failed_count, configured, has_subscriptions).
        configured is False when VAPID keys are missing (so the caller can
        log CONFIGURATION_ERROR instead of pretending the push was sent).
        """
        from .models import PushSubscription

        vapid_private = getattr(settings, "VAPID_PRIVATE_KEY", None)
        vapid_claim_email = getattr(settings, "VAPID_SUBJECT", None) or ""

        if not vapid_private or not vapid_claim_email.startswith("mailto:"):
            logger.warning(
                "PUSH not configured: missing VAPID_PRIVATE_KEY / VAPID_SUBJECT."
            )
            return 0, 0, False, False

        subscriptions = list(PushSubscription.objects.filter(user_id=user_id))
        if not subscriptions:
            return 0, 0, True, False

        sent, failed = 0, 0
        for sub in subscriptions:
            ok, msg = PushNotificationService.send_to_subscription(sub, title, body)
            if ok:
                sent += 1
                logger.info(
                    f"Push sent | user={user_id} | endpoint={sub.endpoint[:60]}..."
                )
            elif msg.startswith("GONE:"):
                failed += 1
                logger.info(
                    f"Push subscription expired (deleting) | user={user_id} "
                    f"| endpoint={sub.endpoint[:60]}..."
                )
                # 404/410: subscription is dead — delete it.
                sub.delete()
            else:
                failed += 1
                logger.warning(
                    f"Push FAILED | user={user_id} "
                    f"| endpoint={sub.endpoint[:60]}... | {msg}"
                )
        return sent, failed, True, True


# Backwards-compat: keep the old name importable, now backed by real push.
class BrowserNotificationService(PushNotificationService):
    pass


# ==========================================================
# Notification Service
# ==========================================================


# ==========================================================
# Notification Service
# ==========================================================

class NotificationService:
    """Orchestrates all notification channels and logs results."""

    MAX_RETRIES = 3

    # Channels a reminder should attempt, honouring the user's per-reminder
    # selection (notify_push / notify_email / notify_sms). Reminders created
    # before this field existed default to True for all channels, so legacy
    # behaviour (attempt every configured channel) is fully preserved.
    @staticmethod
    def _selected_channels(reminder):
        selected = []
        if getattr(reminder, "notify_push", True):
            selected.append("PUSH")
        if getattr(reminder, "notify_email", True):
            selected.append("EMAIL")
        if getattr(reminder, "notify_sms", True):
            selected.append("SMS")
        return selected

    @staticmethod
    def send_all(reminder, sent_channels=None):
        """
        Send notifications through the SELECTED channels (Push, Email, SMS)
        and return a list of NotificationLog objects.

        sent_channels: optional set of channel names already successfully
        delivered for this reminder in an earlier attempt. Channels in this
        set are NOT re-sent (prevents duplicate SMS/push when only the email
        channel is being retried). A channel that previously FAILED is
        retried; a channel the user did not select is never attempted.
        """
        user = reminder.user
        medicine = reminder.medicine
        now = timezone.now()
        logs = []
        selected = NotificationService._selected_channels(reminder)
        already_sent = sent_channels or set()

        logger.info(
            f"NOTIFICATION REQUEST | reminder_id={reminder.id} | "
            f"user_id={user.id} | selected_channels={selected} | "
            f"already_sent_before_this_attempt={sorted(already_sent)}"
        )

        # ── Push Notification (REAL Web Push - independent of Email/SMS) ──
        if "PUSH" in selected and "PUSH" not in already_sent:
            logs.extend(NotificationService._send_push(reminder, user, medicine, now))
        elif "PUSH" in already_sent:
            logger.info(
                f"Reminder {reminder.id}: PUSH already delivered earlier — "
                f"skipping duplicate send."
            )
        else:
            logger.info(
                f"Reminder {reminder.id}: PUSH not selected by user — skipped."
            )

        medicine_name = medicine.medicine_name
        dosage = medicine.dosage
        reminder_time = reminder.reminder_time.strftime("%I:%M %p")
        reminder_date = reminder.reminder_date.strftime("%Y-%m-%d")
        patient_name = user.get_full_name() or user.username
        doctor_name = getattr(medicine, "doctor_name", None)

        # ==========================================================
        # Email Notification (only if the user selected Email)
        # ==========================================================
        if "EMAIL" in selected and "EMAIL" not in already_sent and user.email:
            # DEV-ONLY diagnostic trail (masked, never any credential value)
            logger.info(
                f"EMAIL CHANNEL | reminder_id={reminder.id} | "
                f"request_received=True | "
                f"recipient_validated={'yes' if '@' in user.email else 'NO'} | "
                f"recipient={mask_email(user.email)}"
            )
            # Check SMTP configuration before attempting to send
            email_host = getattr(settings, "EMAIL_HOST", None)
            email_user = getattr(settings, "EMAIL_HOST_USER", None)
            email_password = getattr(settings, "EMAIL_HOST_PASSWORD", None)

            if not all([email_host, email_user, email_password]):
                email_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="EMAIL",
                    recipient=user.email,
                    status="CONFIGURATION_ERROR",
                    error_message="SMTP not configured. Email notification skipped.",
                )
                logs.append(email_log)
                logger.warning(
                    f"Reminder {reminder.id} ({medicine_name}): "
                    f"SMTP not configured, skipping email."
                )
            else:
                subject = f"PillSync - Medicine Reminder: {medicine_name}"
                html_content = build_html_email(
                    patient_name=patient_name,
                    medicine_name=medicine_name,
                    dosage=dosage,
                    reminder_time=reminder_time,
                    reminder_date=reminder_date,
                    doctor_name=doctor_name,
                )
                text_content = build_email_text(
                    patient_name=patient_name,
                    medicine_name=medicine_name,
                    dosage=dosage,
                    reminder_time=reminder_time,
                    reminder_date=reminder_date,
                )

                email_success, email_msg = EmailService.send(
                    reminder_id=reminder.id,
                    medicine_name=medicine_name,
                    recipient_email=user.email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                )

                logger.info(
                    f"EMAIL CHANNEL RESULT | reminder_id={reminder.id} | "
                    f"service_called=True | "
                    f"result={'SUCCESS' if email_success else 'FAILURE'} | "
                    f"reason={email_msg}"
                )

                email_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="EMAIL",
                    recipient=user.email,
                    status="SENT" if email_success else "FAILED",
                    sent_at=now if email_success else None,
                    error_message=None if email_success else email_msg,
                )
                logs.append(email_log)
        elif "EMAIL" in already_sent:
            logger.info(
                f"Reminder {reminder.id}: EMAIL already delivered earlier — "
                f"skipping duplicate send."
            )
        elif "EMAIL" in selected and not user.email:
            logger.warning(
                f"Reminder {reminder.id}: EMAIL selected but user has no "
                f"email address on file — channel skipped."
            )
        else:
            logger.info(
                f"Reminder {reminder.id}: EMAIL not selected by user — skipped."
            )

        # ==========================================================
        # SMS Notification (only if the user selected SMS)
        # ==========================================================
        if "SMS" in selected and "SMS" not in already_sent and user.phone:
            normalized_phone = normalize_phone_number(user.phone)

            # Check Twilio configuration before attempting to send
            twilio_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
            twilio_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
            twilio_from = getattr(settings, "TWILIO_PHONE_NUMBER", None)

            if not all([twilio_sid, twilio_token, twilio_from]):
                sms_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="SMS",
                    recipient=normalized_phone or user.phone,
                    status="CONFIGURATION_ERROR",
                    error_message="Twilio SMS credentials not fully configured",
                )
                logs.append(sms_log)
                logger.warning(
                    f"Reminder {reminder.id}: "
                    f"Twilio SMS not configured, skipping SMS."
                )
            else:
                sms_message = format_sms_message(
                    medicine_name=medicine_name,
                    dosage=dosage,
                    reminder_time=reminder_time,
                )

                logger.info(
                    f"Reminder {reminder.id}: "
                    f"Preparing SMS -> {normalized_phone}"
                )

                sms_success = SMSService.send(
                    phone_number=normalized_phone,
                    message=sms_message,
                )

                sms_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="SMS",
                    recipient=normalized_phone,
                    status="SENT" if sms_success else "FAILED",
                    sent_at=now if sms_success else None,
                    error_message=None if sms_success else "SMS send failed",
                )
                logs.append(sms_log)
        elif "SMS" in already_sent:
            logger.info(
                f"Reminder {reminder.id}: SMS already delivered earlier — "
                f"skipping duplicate send."
            )
        elif "SMS" in selected and not user.phone:
            logger.warning(
                f"Reminder {reminder.id}: SMS selected but user has no "
                f"phone number on file — channel skipped."
            )
        else:
            logger.info(
                f"Reminder {reminder.id}: SMS not selected by user — skipped."
            )

        return logs

    @staticmethod
    def _send_push(reminder, user, medicine, now):
        """
        REAL Web Push via pywebpush, fully independent of Email/SMS.
        A push failure must NEVER block the other channels.
        Returns a list of NotificationLog objects (0 or 1).
        """
        medicine_name = medicine.medicine_name
        dosage = medicine.dosage
        reminder_time = reminder.reminder_time.strftime("%I:%M %p")
        logs = []

        # DEV-ONLY diagnostic trail (never any secret value)
        logger.info(
            f"PUSH CHANNEL | reminder_id={reminder.id} | "
            f"request_received=True | user_id={user.id}"
        )

        try:
            push_sent, push_failed, push_configured, push_has_subs = (
                PushNotificationService.send_to_user(
                    user_id=user.id,
                    title=f"Medicine Reminder: {medicine_name}",
                    body=f"Take {medicine_name} ({dosage}) at {reminder_time}",
                    reminder_id=reminder.id,
                )
            )

            logger.info(
                f"PUSH CHANNEL RESULT | reminder_id={reminder.id} | "
                f"configured={push_configured} | subscriptions_found={push_has_subs} | "
                f"sent={push_sent} | failed={push_failed}"
            )

            if not push_configured:
                push_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="PUSH",
                    recipient=str(user.id),
                    status="CONFIGURATION_ERROR",
                    error_message="VAPID keys not configured. Push skipped.",
                )
                logs.append(push_log)
                logger.warning(
                    f"Reminder {reminder.id}: Push not configured, skipped."
                )
            elif not push_has_subs:
                # Configured but zero subscriptions stored for this user —
                # the frontend has not subscribed this browser yet.
                push_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="PUSH",
                    recipient=str(user.id),
                    status="SKIPPED",
                    error_message="No push subscription stored for user",
                )
                logs.append(push_log)
                logger.info(
                    f"Reminder {reminder.id}: No push subscriptions for "
                    f"user {user.id}; push skipped."
                )
            elif push_sent > 0:
                push_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="PUSH",
                    recipient=str(user.id),
                    status="SENT",
                    sent_at=now,
                    error_message=(
                        f"{push_failed} subscription(s) failed"
                        if push_failed
                        else None
                    ),
                )
                logs.append(push_log)
            else:
                # Configured, subscriptions exist, but delivery failed on
                # every one of them — a REAL failure, never report SENT.
                push_log = NotificationLog.objects.create(
                    user=user,
                    reminder=reminder,
                    channel="PUSH",
                    recipient=str(user.id),
                    status="FAILED",
                    error_message=f"All {push_failed} subscription(s) failed",
                )
                logs.append(push_log)
        except Exception as e:
            # A push failure must NEVER block Email/SMS.
            logger.exception(
                f"Reminder {reminder.id}: Push channel raised: {e}"
            )
            push_log = NotificationLog.objects.create(
                user=user,
                reminder=reminder,
                channel="PUSH",
                recipient=str(user.id),
                status="FAILED",
                error_message=str(e)[:500],
            )
            logs.append(push_log)

        return logs

    @staticmethod
    def fire_reminder(reminder):
        """
        Synchronously fire one reminder through the SELECTED channels.

        Called by the frontend exact-time scheduler at the exact scheduled
        date+time, together with the browser notification. Exactly-once is
        guarded by status/notification_sent inside this method.

        Retry semantics (preserved from the original implementation):
        - Only a real EMAIL failure schedules retries.
        - Channels already delivered in a previous attempt are never
          re-sent (no duplicate SMS/push while email retries run).
        - When the user did NOT select email, the reminder completes as
          TRIGGERED after a single pass (push/sms results are logged).
        """
        now = timezone.now()
        user = reminder.user

        # ── Check if reminder is due ──
        today = timezone.localtime().date()
        current_time = timezone.localtime().time()

        if reminder.reminder_date > today:
            return {"status": "skipped", "reason": "not_due"}

        if reminder.reminder_date == today and reminder.reminder_time > current_time:
            return {"status": "skipped", "reason": "not_due"}

        # ── Already handled? ──
        if reminder.notification_sent or reminder.status in (
            "TRIGGERED", "TAKEN", "MISSED",
        ):
            return {"status": "skipped", "reason": "already_handled"}

        # ── Channels already delivered by a previous attempt ──
        # (a SENT log from an earlier try must never be re-sent)
        previously_sent = set(
            NotificationLog.objects.filter(
                reminder=reminder,
                status="SENT",
            ).values_list("channel", flat=True)
        )

        # ── Send notifications via selected channels ──
        logs = NotificationService.send_all(
            reminder, sent_channels=previously_sent
        )

        # ── Determine email result ──
        email_log = next(
            (log for log in logs if log.channel == "EMAIL"), None
        )
        email_sent = email_log is not None and email_log.status == "SENT"
        email_config_error = (
            email_log is not None
            and email_log.status == "CONFIGURATION_ERROR"
        )
        # No EMAIL log = email not selected, already sent earlier, or the
        # user has no email address — none of these are retryable failures.
        no_email_address = email_log is None

        email_error = (
            email_log.error_message if email_log and email_log.error_message else None
        )

        # ── Handle email failure / config error / no email ──
        if not email_sent:
            if email_config_error or no_email_address:
                # Config error or no email address — not retryable
                reminder.status = "TRIGGERED"
                reminder.notification_sent = True
                reminder.save(
                    update_fields=["status", "notification_sent"]
                )
                return {
                    "status": "triggered",
                    "email_sent": False,
                    "email_error": email_error,
                }

            reminder.retry_count += 1
            if reminder.retry_count >= NotificationService.MAX_RETRIES:
                # Retries exhausted — close the reminder
                reminder.status = "TRIGGERED"
                reminder.notification_sent = True
                reminder.save(
                    update_fields=[
                        "status",
                        "notification_sent",
                        "retry_count",
                    ]
                )
                return {
                    "status": "triggered",
                    "email_sent": False,
                    "email_error": email_error,
                }

            reminder.save(update_fields=["retry_count"])
            return {
                "status": "email_failed_retry",
                "email_sent": False,
                "email_error": email_error,
            }

        # ── Success ──
        reminder.status = "TRIGGERED"
        reminder.notification_sent = True
        reminder.save(update_fields=["status", "notification_sent"])
        return {"status": "triggered", "email_sent": True, "email_error": None}

    @staticmethod
    def process_due_reminders(user):
        """
        Process all due reminders for a user (list catch-up).

        Fires any due PENDING reminders for this user right now so
        reminders execute even when Celery Beat / Worker / Redis are
        not running.
        """
        now = timezone.localtime()
        today = now.date()
        current_time = now.time()

        # Mark old pending reminders as missed
        Reminder.objects.filter(
            user=user,
            reminder_date__lt=today,
            status="PENDING",
            notification_sent=False,
        ).update(status="MISSED")

        # Find due reminders
        due_reminders = Reminder.objects.filter(
            user=user,
            reminder_date=today,
            reminder_time__lte=current_time,
            status="PENDING",
            notification_sent=False,
        )

        fired = 0
        for reminder in due_reminders:
            result = NotificationService.fire_reminder(reminder)
            if result.get("status") == "triggered":
                fired += 1

        return fired

    @staticmethod
    def get_pending_push_notifications(user_id):
        """Get recent push notifications for browser display."""
        recent_logs = (
            NotificationLog.objects.filter(
                user_id=user_id,
                channel="PUSH",
                created_at__gte=timezone.now() - timedelta(hours=24),
            )
            .select_related("reminder__medicine")
            .order_by("-created_at")[:50]
        )

        return [
            {
                "id": log.id,
                "title": (
                    f"Medicine Reminder: "
                    f"{log.reminder.medicine.medicine_name}"
                    if log.reminder and log.reminder.medicine
                    else "Medicine Reminder"
                ),
                "body": (
                    f"Reminder for {log.reminder.medicine.medicine_name}"
                    if log.reminder and log.reminder.medicine
                    else ""
                ),
                "reminder_id": log.reminder_id,
                "created_at": log.created_at,
                "status": log.status,
            }
            for log in recent_logs
        ]
