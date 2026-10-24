"""
Celery tasks for the PillSync reminder system.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Reminder, NotificationLog
from .services import NotificationService, mask_email, mask_phone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reminder_notifications(self, reminder_id):
    logger.info(f"TASK STARTED: send_reminder_notifications | Reminder ID={reminder_id}")

    try:
        reminder = Reminder.objects.select_related("user", "medicine").get(id=reminder_id)
    except Reminder.DoesNotExist:
        logger.error(f"Reminder {reminder_id} not found")
        logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=REMINDER_NOT_FOUND")
        return {"status": "error", "message": f"Reminder {reminder_id} not found"}

    now = timezone.now()
    user = reminder.user
    medicine = reminder.medicine
    medicine_name = medicine.medicine_name
    recipient_email = user.email
    recipient_phone = user.phone

    logger.info(
        f"TASK EXECUTING: send_reminder_notifications | "
        f"Reminder ID={reminder_id} | "
        f"User ID={user.id} | "
        f"User Email={mask_email(recipient_email)} | "
        f"User Phone={mask_phone(recipient_phone)} | "
        f"Current Time={now.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
        f"Reminder Time={reminder.reminder_time} | "
        f"Reminder Date={reminder.reminder_date} | "
        f"Medicine={medicine_name} | "
        f"notification_sent={reminder.notification_sent} | "
        f"retry_count={reminder.retry_count}"
    )

    if reminder.notification_sent:
        logger.info(f"Reminder {reminder_id} already sent. Skipping.")
        logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=ALREADY_SENT")
        return {"status": "skipped", "message": "Already sent"}

    if not recipient_email:
        # No email to send — NOT a failure. send_all() below skips the email
        # channel and still attempts SMS/Push, and the reminder is still
        # marked TRIGGERED so it never fires again.
        logger.warning(
            f"Reminder ID={reminder_id} | "
            f"User ID={user.id} | "
            f"Medicine Name={medicine_name} | "
            f"Recipient Email=NONE | "
            f"Reason=User has no email address — skipping email channel only"
        )

    logger.info(
        f"TASK CALLING: NotificationService.send_all | "
        f"Reminder ID={reminder_id} | "
        f"Recipient Email={mask_email(recipient_email)} | "
        f"Recipient Phone={mask_phone(recipient_phone)}"
    )

    try:
        # Channels already delivered by a previous attempt must never be
        # re-sent (prevents duplicate SMS/push while email retries run).
        previously_sent = set(
            NotificationLog.objects.filter(
                reminder=reminder,
                status="SENT",
            ).values_list("channel", flat=True)
        )
        logs = NotificationService.send_all(
            reminder, sent_channels=previously_sent
        )

        logger.info(
            f"TASK RETURNED: NotificationService.send_all | "
            f"Reminder ID={reminder_id} | "
            f"Logs count={len(logs)}"
        )

        # Find the email log to determine success/failure
        email_log = next((log for log in logs if log.channel == "EMAIL"), None)
        email_success = email_log is not None and email_log.status == "SENT"
        smtp_response = "OK" if email_success else (
            email_log.error_message if email_log else "NO_EMAIL_LOG"
        )
        notification_status = email_log.status if email_log else "NO_EMAIL_LOG"

        # Also get SMS/Twilio response info
        sms_log = next((log for log in logs if log.channel == "SMS"), None)
        twilio_response = sms_log.error_message if sms_log and sms_log.status == "FAILED" else "OK"

        # "No email to send" (no EMAIL log) or SMTP not configured are NOT
        # retryable — the reminder is processed exactly once. Only a real SMTP
        # failure (auth/network) is retried, capped at MAX_RETRIES; once the
        # budget is exhausted the reminder is marked TRIGGERED so the beat
        # scheduler never re-fires it (no duplicate SMS/push).
        email_not_retryable = email_log is None or (
            email_log.status == "CONFIGURATION_ERROR"
        )

        retry = False
        if email_success or email_not_retryable:
            reminder.status = "TRIGGERED"
            reminder.notification_sent = True
            reminder.save(update_fields=["status", "notification_sent"])
        elif reminder.retry_count < NotificationService.MAX_RETRIES:
            reminder.retry_count += 1
            reminder.save(update_fields=["retry_count"])
            retry = True
        else:
            # Retry budget exhausted — close the reminder.
            reminder.status = "TRIGGERED"
            reminder.notification_sent = True
            reminder.save(
                update_fields=["status", "notification_sent", "retry_count"]
            )

        success = sum(1 for log in logs if log.status == "SENT")
        failed = sum(1 for log in logs if log.status == "FAILED")

        logger.info(
            f"TASK CHANNEL RESULTS | "
            f"Reminder ID={reminder_id} | "
            f"User ID={user.id} | "
            f"Recipient Email={mask_email(recipient_email)} | "
            f"Recipient Phone={mask_phone(recipient_phone)} | "
            f"SMTP Response={smtp_response} | "
            f"Twilio Response={twilio_response} | "
            f"Notification Status={notification_status} | "
            f"Channels: {success} sent, {failed} failed"
        )

        if retry:
            logger.info(
                f"Reminder ID={reminder_id}: Scheduling retry #{reminder.retry_count}"
            )
            logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=RETRY #{reminder.retry_count}")
            raise self.retry(countdown=60 * (reminder.retry_count + 1))

        logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=COMPLETED")
        return {
            "status": "success" if email_success else "partial_failure",
            "reminder_id": reminder_id,
            "smtp_response": smtp_response,
            "notification_status": notification_status,
            "success": success,
            "failed": failed,
        }

    except Reminder.DoesNotExist:
        logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=DELETED")
        return {"status": "error", "message": "Reminder deleted"}
    except Exception as exc:
        logger.error(
            f"TASK EXCEPTION: send_reminder_notifications | "
            f"Reminder ID={reminder_id} | "
            f"User ID={user.id if 'user' in dir() else 'N/A'} | "
            f"Recipient Email={mask_email(recipient_email) if 'recipient_email' in dir() else 'N/A'} | "
            f"Recipient Phone={mask_phone(recipient_phone) if 'recipient_phone' in dir() else 'N/A'} | "
            f"Exception={exc}",
            exc_info=True
        )
        if reminder.retry_count < NotificationService.MAX_RETRIES:
            reminder.retry_count += 1
            reminder.save(update_fields=["retry_count"])
            logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=RETRY_AFTER_EXCEPTION #{reminder.retry_count}")
            raise self.retry(exc=exc, countdown=60 * (reminder.retry_count + 1))
        logger.info(f"TASK FINISHED: send_reminder_notifications | Reminder ID={reminder_id} | Status=FAILED")
        return {"status": "failed", "reminder_id": reminder_id, "error": str(exc)}


@shared_task
def check_and_send_reminders():
    # Reminder date/time are stored as the user's LOCAL wall-clock time.
    # timezone.localtime() converts to the configured TIME_ZONE (Asia/Kolkata)
    # so the comparison below uses the same local clock the user selected.
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()

    logger.info(
        f"BEAT TASK STARTED: check_and_send_reminders | "
        f"Current Time={now.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
        f"Date={today} | "
        f"Time={current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}"
    )

    # Find all pending reminders for today whose time has arrived
    due_reminders = Reminder.objects.select_related("user", "medicine").filter(
        reminder_date=today,
        reminder_time__lte=current_time,
        status="PENDING",
        notification_sent=False,
    )

    due_count = due_reminders.count()
    logger.info(f"BEAT TASK: Found {due_count} due reminder(s) for {today}")

    # Debug log each due reminder
    for reminder in due_reminders:
        user = reminder.user
        logger.info(
            f"BEAT TASK DISPATCHING: send_reminder_notifications | "
            f"Reminder ID={reminder.id} | "
            f"User ID={user.id} | "
            f"User Email={mask_email(user.email)} | "
            f"User Phone={mask_phone(user.phone)} | "
            f"Reminder Time={reminder.reminder_time} | "
            f"Medicine={reminder.medicine.medicine_name}"
        )
        send_reminder_notifications.delay(reminder.id)

    # Mark missed reminders
    five_minutes_ago = (now - timedelta(minutes=5)).time()
    missed = Reminder.objects.filter(
        reminder_date=today,
        reminder_time__lte=five_minutes_ago,
        status="PENDING",
        notification_sent=False,
    )
    missed_count = missed.count()
    if missed_count > 0:
        missed.update(status="MISSED")
        logger.info(f"BEAT TASK: Marked {missed_count} old reminder(s) as MISSED")

    # Handle recurring reminders
    for reminder in due_reminders:
        _create_next_recurring(reminder)

    # Handle expired snoozed reminders
    expired_snoozed = Reminder.objects.filter(
        reminder_date=today,
        status="SNOOZED",
        snoozed_until__lte=now,
    )
    for reminder in expired_snoozed:
        reminder.status = "PENDING"
        reminder.snoozed_until = None
        reminder.save(update_fields=["status", "snoozed_until"])
        logger.info(f"BEAT TASK: Snoozed reminder {reminder.id} re-activated to PENDING")

    logger.info(
        f"BEAT TASK FINISHED: check_and_send_reminders | "
        f"Due={due_count} | "
        f"Missed={missed_count}"
    )

    return {"status": "success", "due": due_count, "missed": missed_count}


def _create_next_recurring(reminder):
    if not reminder.is_recurring:
        return
    interval = (reminder.recurring_interval or "").lower()
    if interval == "daily":
        next_date = reminder.reminder_date + timedelta(days=1)
    elif interval == "weekly":
        next_date = reminder.reminder_date + timedelta(weeks=1)
    elif interval == "monthly":
        next_date = reminder.reminder_date + timedelta(days=30)
    else:
        return
    exists = Reminder.objects.filter(
        user=reminder.user,
        medicine=reminder.medicine,
        reminder_date=next_date,
        reminder_time=reminder.reminder_time,
    ).exists()
    if not exists:
        Reminder.objects.create(
            user=reminder.user,
            medicine=reminder.medicine,
            reminder_time=reminder.reminder_time,
            reminder_date=next_date,
            status="PENDING",
            is_recurring=True,
            recurring_interval=reminder.recurring_interval,
        )
        logger.info(f"Created recurring reminder for {reminder.medicine.medicine_name} on {next_date}")


@shared_task
def handle_missed_reminders():
    now = timezone.localtime()
    old = Reminder.objects.filter(
        reminder_date__lt=now.date(),
        status="PENDING",
        notification_sent=False,
    ).update(status="MISSED")
    two_hours_ago = (now - timedelta(hours=2)).time()
    today_missed = Reminder.objects.filter(
        reminder_date=now.date(),
        reminder_time__lte=two_hours_ago,
        status="PENDING",
        notification_sent=False,
    ).update(status="MISSED")
    total = old + today_missed
    if total > 0:
        logger.info(f"Cleanup: marked {total} old reminder(s) as MISSED")
    return {"status": "success", "missed": total}


@shared_task
def cleanup_notification_logs():
    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = NotificationLog.objects.filter(created_at__lt=cutoff).delete()
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old notification log(s)")
    return {"status": "success", "deleted": deleted}
