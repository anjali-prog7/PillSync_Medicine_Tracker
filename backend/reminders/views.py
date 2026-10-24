import logging

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView

from django.utils import timezone

from .models import Reminder, NotificationLog, PushSubscription
from .serializers import ReminderSerializer, NotificationLogSerializer, PushSubscriptionSerializer
from .services import NotificationService, mask_email, mask_phone

logger = logging.getLogger(__name__)


class ReminderViewSet(viewsets.ModelViewSet):

    serializer_class = ReminderSerializer
    permission_classes = [IsAuthenticated]

    # Reminder pks are integers. Restricting the detail-route lookup prevents
    # the empty-prefix detail regex ^(?P<pk>[^/.]+)/$ from swallowing other
    # top-level segments (e.g. "notification-logs") and returning 404.
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        # ── Synchronous catch-up scheduler ─────────────────────────────────
        # Fires any due PENDING reminders for this user right now (email +
        # status=TRIGGERED) so reminders execute even when Celery Beat /
        # Worker / Redis are not running. Reminders that are not due yet are
        # never fired here (fire_reminder guards the time comparison).
        # The frontend exact-time scheduler also calls POST /{id}/trigger/ at
        # the exact fire moment, so this list is only the safety net.
        fired = NotificationService.process_due_reminders(request.user)
        if fired:
            logger.info(f"LIST CATCH-UP: fired {fired} due reminder(s) for user {request.user.id}")
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def trigger(self, request, pk=None):
        """
        Synchronously fire one reminder: send email and mark it TRIGGERED.

        Called by the frontend exact-time scheduler at the exact scheduled
        date+time, together with the browser notification. Exactly-once is
        guarded by status/notification_sent inside NotificationService.
        """
        reminder = self.get_object()
        result = NotificationService.fire_reminder(reminder)
        return Response(result)

    def perform_create(self, serializer):
        reminder = serializer.save(user=self.request.user)

        # ── Log creation details ──
        now = timezone.now()
        logger.info(
            f"REMINDER CREATED | "
            f"Reminder ID={reminder.id} | "
            f"User ID={reminder.user.id} | "
            f"User Email={mask_email(reminder.user.email)} | "
            f"User Phone={mask_phone(reminder.user.phone)} | "
            f"Current Time={now.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
            f"Reminder Time={reminder.reminder_time} | "
            f"Reminder Date={reminder.reminder_date} | "
            f"Medicine={reminder.medicine.medicine_name} | "
            f"Scheduled For=Celery Beat (every 60s)"
        )

        # NOTE: No email/notification is sent here.
        # The Celery beat scheduler (tasks.check_and_send_reminders) is the
        # ONLY component that triggers notifications, and only once the
        # stored Reminder Date + Time has actually been reached.
        return reminder

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Return all pending (untaken) reminders for today."""
        from django.utils import timezone
        today = timezone.localtime().date()
        reminders = self.get_queryset().filter(
            reminder_date=today,
            status="PENDING",
        ).order_by("reminder_time")
        serializer = self.get_serializer(reminders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"])
    def mark_taken(self, request, pk=None):
        """Mark a reminder as TAKEN."""
        reminder = self.get_object()
        reminder.status = "TAKEN"
        reminder.save(update_fields=["status"])
        return Response({"status": "TAKEN"})

    @action(detail=True, methods=["patch"])
    def mark_missed(self, request, pk=None):
        """Mark a reminder as MISSED."""
        reminder = self.get_object()
        reminder.status = "MISSED"
        reminder.save(update_fields=["status"])
        return Response({"status": "MISSED"})

    @action(detail=True, methods=["patch"])
    def snooze(self, request, pk=None):
        """Snooze a reminder for a given duration (default: 10 minutes)."""
        from django.utils import timezone
        from datetime import timedelta

        minutes = request.data.get("minutes", 10)
        reminder = self.get_object()
        reminder.status = "SNOOZED"
        reminder.snoozed_until = timezone.now() + timedelta(minutes=int(minutes))
        reminder.notification_sent = False
        reminder.save(update_fields=["status", "snoozed_until", "notification_sent"])
        return Response({"status": "SNOOZED", "snoozed_until": reminder.snoozed_until})


class PushSubscriptionView(APIView):
    """
    POST   /api/reminders/push/subscribe/   - store a browser PushSubscription
    DELETE /api/reminders/push/subscribe/   - remove it (user unsubscribed)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            sub = serializer.save()
            logger.info(
                f"PUSH SUBSCRIBED | user={request.user.id} "
                f"| endpoint={sub.endpoint[:60]}..."
            )
            return Response(
                {"status": "subscribed", "id": sub.id},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        endpoint = request.data.get("endpoint", "")
        deleted, _ = PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint
        ).delete()
        if deleted:
            return Response({"status": "unsubscribed"})
        return Response(
            {"status": "not_found"}, status=status.HTTP_404_NOT_FOUND
        )


class PushVapidKeyView(APIView):
    """GET /api/reminders/push/vapid-key/ - public VAPID key for pushManager.subscribe()."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings as dj_settings
        key = getattr(dj_settings, "VAPID_PUBLIC_KEY", "")
        if not key:
            return Response(
                {"error": "VAPID_PUBLIC_KEY not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"publicKey": key})


class PushTestView(APIView):
    """
    POST /api/reminders/push/test/ - send a real test push right now.
    Lets the user verify end-to-end push delivery without waiting for a
    reminder to fire. Uses the same PushNotificationService as reminders.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services import PushNotificationService

        # send_to_user returns (sent, failed, configured, has_subscriptions).
        # The previous 3-value unpack raised ValueError -> HTTP 500 whenever
        # this endpoint was called. Fixed to unpack all four values.
        sent, failed, configured, has_subs = PushNotificationService.send_to_user(
            user_id=request.user.id,
            title="PillSync Test Push",
            body="If you can read this, real Web Push is working!",
        )
        if not configured:
            return Response(
                {"status": "error",
                 "detail": "VAPID keys not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not has_subs or sent == 0:
            return Response(
                {"status": "error",
                 "detail": (
                     "No push subscription stored for this user. "
                     "Enable notifications in the browser first."
                 )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"status": "sent", "sent": sent, "failed": failed}
        )


class EmailConfigCheckView(APIView):
    """
    GET /api/reminders/email-config-check/

    SAFE diagnostic endpoint for the frontend: reports whether the server's
    SMTP configuration is complete — WITHOUT ever exposing any credential
    value. Only boolean presence flags are returned.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings as dj_settings

        email_host = getattr(dj_settings, "EMAIL_HOST", None)
        email_user = getattr(dj_settings, "EMAIL_HOST_USER", None)
        email_password = getattr(dj_settings, "EMAIL_HOST_PASSWORD", None)

        configured = bool(email_host and email_user and email_password)
        # DEFAULT_FROM_EMAIL falls back to EMAIL_HOST_USER in settings.py,
        # so it is considered fine whenever EMAIL_HOST_USER is present.
        from_ok = bool(
            getattr(dj_settings, "DEFAULT_FROM_EMAIL", "") or email_user
        )
        return Response(
            {
                "configured": configured,
                "missing": []
                if configured
                else [
                    name
                    for name, val in (
                        ("EMAIL_HOST", email_host),
                        ("EMAIL_HOST_USER", email_user),
                        ("EMAIL_HOST_PASSWORD", email_password),
                    )
                    if not val
                ],
                "from_matches_user": bool(from_ok and email_user),
                "hint": (
                    "Gmail requires a 16-char App Password in "
                    "EMAIL_HOST_PASSWORD (backend/.env) with 2FA enabled."
                    if not configured
                    else None
                ),
            }
        )


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """View notification logs (read-only)."""

    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]

    # NotificationLog pks are integers — keep "pending-push" and other
    # non-numeric paths from being treated as a pk.
    lookup_value_regex = r"[0-9]+"

    def get_queryset(self):
        return NotificationLog.objects.filter(user=self.request.user).select_related("reminder__medicine")

    @action(detail=False, methods=["get"], url_path="pending-push")
    def pending_push(self, request):
        """Return recent push notifications for browser display."""
        from .services import NotificationService
        notifications = NotificationService.get_pending_push_notifications(
            request.user.id
        )
        return Response(notifications)
