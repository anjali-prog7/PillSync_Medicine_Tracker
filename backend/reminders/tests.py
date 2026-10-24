"""
Regression tests for the Reminder execution fix.

These tests verify the synchronous (non-Celery) execution path added to make
reminders actually trigger at the scheduled local date + time:

    1. Creating a reminder must NOT send any email.
    2. fire_reminder() sends email + marks TRIGGERED only when due.
    3. fire_reminder() skips reminders that are not due yet.
    4. Exactly-once: a fired reminder is never fired again.
    5. List catch-up (process_due_reminders) fires due reminders on page load.
    6. The trigger endpoint returns the same result as fire_reminder().
"""

from datetime import time as time_cls
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from medicines.models import Medicine
from .models import NotificationLog, Reminder, PushSubscription
from .services import NotificationService

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    # Prevent any real Twilio calls during tests (user has no phone anyway)
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_PHONE_NUMBER="",
    # Prevent any real Web Push calls during tests. VAPID keys may exist in
    # backend/.env — tests must never hit a real browser push service.
    VAPID_PUBLIC_KEY="",
    VAPID_PRIVATE_KEY="",
)
class ReminderExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="remindertest",
            email="remindertest@example.com",
            password="testpass123",
        )
        self.medicine = Medicine.objects.create(
            user=self.user,
            medicine_name="Paracetamol",
            medicine_type="TABLET",
            dosage="500mg",
            frequency="Morning",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _make_reminder(self, reminder_date=None, reminder_time=None, status="PENDING"):
        return Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=reminder_date or timezone.localdate(),
            reminder_time=reminder_time or time_cls(9, 0),
            status=status,
        )

    # ── 1. Email must NOT be sent during reminder creation ──────────────
    def test_create_reminder_sends_no_email(self):
        response = self.client.post(
            "/api/reminders/",
            {
                "medicine": self.medicine.id,
                "reminder_time": "18:30:00",
                "reminder_date": timezone.localdate().isoformat(),
                "status": "PENDING",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 0, "No email may be sent at creation")
        reminder = Reminder.objects.get(id=response.data["id"])
        self.assertEqual(reminder.status, "PENDING")
        self.assertFalse(reminder.notification_sent)

    # ── 2. fire_reminder fires a due reminder + marks TRIGGERED ─────────
    def test_fire_reminder_when_due(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        self.assertTrue(result["email_sent"])

        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        self.assertTrue(reminder.notification_sent)

        # Email + push logs recorded
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PillSync", mail.outbox[0].subject)
        self.assertIn("Paracetamol", mail.outbox[0].body)
        self.assertTrue(
            NotificationLog.objects.filter(
                reminder=reminder, channel="EMAIL", status="SENT"
            ).exists()
        )

    # ── 3. fire_reminder skips a reminder that is not due yet ───────────
    def test_fire_reminder_skips_not_due(self):
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        reminder = self._make_reminder(reminder_date=tomorrow)
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "not_due")

        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "PENDING")
        self.assertFalse(reminder.notification_sent)
        self.assertEqual(len(mail.outbox), 0)

    # ── 4. Exactly-once ─────────────────────────────────────────────────
    def test_fire_reminder_exactly_once(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        first = NotificationService.fire_reminder(reminder)
        self.assertEqual(first["status"], "triggered")

        # Second call: already TRIGGERED / notification_sent -> skipped
        reminder.refresh_from_db()
        second = NotificationService.fire_reminder(reminder)
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "already_handled")

        self.assertEqual(len(mail.outbox), 1, "Email must be sent exactly once")

    # ── 5. List catch-up fires due reminders on page load ───────────────
    def test_list_catch_up_fires_due_reminders(self):
        now = timezone.localtime()
        due = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        not_due = self._make_reminder(reminder_date=tomorrow)

        response = self.client.get("/api/reminders/")
        self.assertEqual(response.status_code, 200)

        due.refresh_from_db()
        not_due.refresh_from_db()
        self.assertEqual(due.status, "TRIGGERED")
        self.assertEqual(not_due.status, "PENDING", "Future reminder must not fire")
        self.assertEqual(len(mail.outbox), 1)

    # ── 6. Trigger endpoint behaves like fire_reminder ──────────────────
    def test_trigger_endpoint(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        response = self.client.post(f"/api/reminders/{reminder.id}/trigger/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "triggered")
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        self.assertEqual(len(mail.outbox), 1)

    # ── 7. Stale past-date PENDING reminders are marked MISSED ──────────
    def test_process_due_marks_old_reminders_missed(self):
        past = timezone.localdate() - timezone.timedelta(days=2)
        stale = self._make_reminder(reminder_date=past)
        NotificationService.process_due_reminders(self.user)
        stale.refresh_from_db()
        self.assertEqual(stale.status, "MISSED")

    # ── 8. Existing endpoints still work after the list() override ──────
    def test_existing_endpoints_unchanged(self):
        reminder = self._make_reminder()

        # mark_taken
        r = self.client.patch(f"/api/reminders/{reminder.id}/mark_taken/")
        self.assertEqual(r.status_code, 200)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TAKEN")

        # pending list (today)
        r = self.client.get("/api/reminders/pending/")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, list)

        # snooze
        r = self.client.patch(f"/api/reminders/{reminder.id}/snooze/")
        self.assertEqual(r.status_code, 200)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "SNOOZED")

        # mark_missed
        reminder.status = "PENDING"
        reminder.save(update_fields=["status"])
        r = self.client.patch(f"/api/reminders/{reminder.id}/mark_missed/")
        self.assertEqual(r.status_code, 200)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "MISSED")

    # ── 9. Trigger is exactly-once even when called twice quickly ───────
    def test_trigger_endpoint_exactly_once(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        r1 = self.client.post(f"/api/reminders/{reminder.id}/trigger/")
        r2 = self.client.post(f"/api/reminders/{reminder.id}/trigger/")
        self.assertEqual(r1.data["status"], "triggered")
        self.assertEqual(r2.data["status"], "skipped")
        self.assertEqual(len(mail.outbox), 1, "Email must be sent exactly once")

    # ── 10. User without email: reminder still fires → TRIGGERED ────────
    def test_fire_reminder_without_email_marks_triggered(self):
        no_email_user = User.objects.create_user(
            username="noemailuser",
            email="",
            password="testpass123",
        )
        medicine = Medicine.objects.create(
            user=no_email_user,
            medicine_name="Dolo",
            medicine_type="TABLET",
            dosage="650mg",
            frequency="Morning",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )
        now = timezone.localtime()
        reminder = Reminder.objects.create(
            user=no_email_user,
            medicine=medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
        )
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        self.assertTrue(reminder.notification_sent)

    # ── 11. Email failure keeps reminder PENDING for retry ──────────────
    def test_fire_reminder_email_failure_keeps_pending(self):
        from unittest import mock

        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        # Force the email to fail; other channels stay unaffected.
        with mock.patch.object(
            NotificationService, "send_all", autospec=True
        ) as fake_send:
            fake_logs = [
                NotificationLog(
                    user=self.user,
                    reminder=reminder,
                    channel="EMAIL",
                    recipient=self.user.email,
                    status="FAILED",
                    error_message="SMTP down",
                )
            ]
            fake_send.return_value = fake_logs
            result = NotificationService.fire_reminder(reminder)

        self.assertEqual(result["status"], "email_failed_retry")
        self.assertFalse(result["email_sent"])
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "PENDING", "Must stay PENDING for retry")
        self.assertFalse(reminder.notification_sent)
        self.assertEqual(reminder.retry_count, 1)

    # ── 12. Email retries are capped — reminder closes as TRIGGERED ──────
    def test_fire_reminder_email_retries_capped_at_triggered(self):
        from unittest import mock

        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )

        def fake_send(_reminder, sent_channels=None):
            reminder.refresh_from_db()
            return [
                NotificationLog(
                    user=self.user,
                    reminder=reminder,
                    channel="EMAIL",
                    recipient=self.user.email,
                    status="FAILED",
                    error_message="SMTP auth rejected",
                )
            ]

        with mock.patch.object(
            NotificationService, "send_all", autospec=True, side_effect=fake_send
        ):
            for attempt in range(NotificationService.MAX_RETRIES):
                reminder.refresh_from_db()
                result = NotificationService.fire_reminder(reminder)
                if attempt < NotificationService.MAX_RETRIES - 1:
                    self.assertEqual(result["status"], "email_failed_retry")
                else:
                    # Last retry: reminder must close as TRIGGERED so the list
                    # catch-up never re-fires it (no duplicate SMS/push).
                    self.assertEqual(result["status"], "triggered")

        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        self.assertTrue(reminder.notification_sent)
        self.assertEqual(reminder.retry_count, NotificationService.MAX_RETRIES)

    # ── 13. Missing SMTP config → CONFIGURATION_ERROR, still TRIGGERED ───
    @override_settings(EMAIL_HOST=None, EMAIL_HOST_USER=None, EMAIL_HOST_PASSWORD=None)
    def test_fire_reminder_without_smtp_config_marks_triggered(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        log = NotificationLog.objects.get(
            reminder=reminder, channel="EMAIL"
        )
        self.assertEqual(log.status, "CONFIGURATION_ERROR")
        self.assertIn("SMTP not configured", log.error_message)

    # ── 14. Missing Twilio config → CONFIGURATION_ERROR, reminder TRIGGERED ─
    @override_settings(
        TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", TWILIO_PHONE_NUMBER=""
    )
    def test_sms_without_twilio_config_is_logged_not_crash(self):
        user = self.user
        user.phone = "+919876543210"
        user.save(update_fields=["phone"])
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        # Must NOT raise and must still complete the reminder.
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")
        sms_log = NotificationLog.objects.get(
            reminder=reminder, channel="SMS"
        )
        self.assertEqual(sms_log.status, "CONFIGURATION_ERROR")
        self.assertIn("not fully configured", sms_log.error_message)
        # Email still worked independently.
        self.assertTrue(
            NotificationLog.objects.filter(
                reminder=reminder, channel="EMAIL", status="SENT"
            ).exists()
        )

    # ── 15. Notification-log API is exposed and user-scoped ──────────────
    def test_notification_logs_endpoint_returns_own_logs_only(self):
        now = timezone.localtime()
        reminder = self._make_reminder(
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
        )
        NotificationService.fire_reminder(reminder)

        # The endpoint the frontend calls must NOT 404.
        response = self.client.get("/api/reminders/notification-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(len(response.data) > 0)

        # pending-push feed (dash URL, not underscore) must work too.
        push = self.client.get(
            "/api/reminders/notification-logs/pending-push/"
        )
        self.assertEqual(push.status_code, 200)
        self.assertTrue(isinstance(push.data, list))

        # A different user must not see the first user's logs.
        other = User.objects.create_user(
            username="otheruser", email="other@example.com", password="x"
        )
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        other_response = other_client.get("/api/reminders/notification-logs/")
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.data, [])


@override_settings(
    VAPID_PUBLIC_KEY="",
    VAPID_PRIVATE_KEY="",
    VAPID_SUBJECT="",
)
class PushSubscriptionFlowTests(TestCase):
    """Tests for the REAL Web Push flow (subscription + delivery + logging)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="pushtest",
            email="pushtest@example.com",
            password="testpass123",
        )
        self.medicine = Medicine.objects.create(
            user=self.user,
            medicine_name="Ibuprofen",
            medicine_type="TABLET",
            dosage="400mg",
            frequency="Morning",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _subscribe(self):
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
            "keys": {
                "p256dh": "B" * 87,
                "auth": "a" * 24,
            },
            "user_agent": "TestBrowser/1.0",
        }
        return self.client.post(
            "/api/reminders/push/subscribe/", payload, format="json"
        )

    # ── P1. VAPID public key endpoint serves the key ────────────────────
    @override_settings(VAPID_PUBLIC_KEY="test-public-key-abc")
    def test_vapid_key_endpoint(self):
        response = self.client.get("/api/reminders/push/vapid-key/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["publicKey"], "test-public-key-abc")

    # ── P2. Subscribe stores the subscription (upsert by endpoint) ──────
    def test_subscribe_stores_subscription(self):
        response = self._subscribe()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.user.push_subscriptions.count(), 1)

        # Re-subscribing with the same endpoint updates, not duplicates.
        self._subscribe()
        self.assertEqual(self.user.push_subscriptions.count(), 1)

    # ── P3. Another user's subscription is not overwritten ─────────────
    def test_subscribe_different_users_same_endpoint_conflict(self):
        self._subscribe()
        other = User.objects.create_user(
            username="pushother", email="pushother@example.com", password="x"
        )
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/other-endpoint",
            "keys": {"p256dh": "C" * 87, "auth": "b" * 24},
        }
        r = other_client.post("/api/reminders/push/subscribe/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            PushSubscription.objects.filter(user=other).count(), 1
        )

    # ── P4. Missing keys are rejected ───────────────────────────────────
    def test_subscribe_requires_keys(self):
        payload = {"endpoint": "https://fcm.googleapis.com/fcm/send/x"}
        response = self.client.post(
            "/api/reminders/push/subscribe/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)

    # ── P5. Unsubscribe removes the subscription ─────────────────────────
    def test_unsubscribe(self):
        self._subscribe()
        response = self.client.delete(
            "/api/reminders/push/subscribe/",
            {"endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.push_subscriptions.count(), 0)

    # ── P6. No subscription + reminder fires -> PUSH log SKIPPED, no crash
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_reminder_without_subscription_logs_skipped(self):
        now = timezone.localtime()
        reminder = Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
        )
        NotificationService.fire_reminder(reminder)
        push_log = NotificationLog.objects.get(
            reminder=reminder, channel="PUSH"
        )
        self.assertEqual(push_log.status, "SKIPPED")
        self.assertIn("No push subscription", push_log.error_message)

    # ── P7. With a subscription + VAPID, reminder sends REAL push
    #        (mocked at the network boundary: pywebpush.webpush) ─────────
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_reminder_with_subscription_sends_real_push(self):
        from unittest import mock

        self._subscribe()
        now = timezone.localtime()
        reminder = Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
        )

        with mock.patch(
            "pywebpush.webpush"
        ) as fake_webpush:
            NotificationService.fire_reminder(reminder)

        fake_webpush.assert_called_once()
        call_kwargs = fake_webpush.call_args.kwargs
        self.assertEqual(
            call_kwargs["subscription_info"]["endpoint"],
            "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
        )
        self.assertEqual(
            call_kwargs["vapid_claims"]["sub"], "mailto:admin@pillsync.com"
        )
        push_log = NotificationLog.objects.get(
            reminder=reminder, channel="PUSH"
        )
        self.assertEqual(push_log.status, "SENT")

    # ── P8. Expired subscription (410) is deleted, reminder still fires ──
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_expired_subscription_deleted(self):
        from unittest import mock
        from pywebpush import WebPushException

        self._subscribe()
        now = timezone.localtime()
        reminder = Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
        )

        fake_response = mock.Mock(status_code=410)
        with mock.patch(
            "pywebpush.webpush",
            side_effect=WebPushException(
                "Gone", response=fake_response
            ),
        ):
            NotificationService.fire_reminder(reminder)

        # Dead subscription removed.
        self.assertEqual(self.user.push_subscriptions.count(), 0)
        # But the reminder still completed (other channels unaffected).
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "TRIGGERED")

    # ── P9. Missing VAPID config -> CONFIGURATION_ERROR, no fake SENT ────
    def test_reminder_without_vapid_config_logs_configuration_error(self):
        self._subscribe()
        now = timezone.localtime()
        reminder = Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
        )
        NotificationService.fire_reminder(reminder)
        push_log = NotificationLog.objects.get(
            reminder=reminder, channel="PUSH"
        )
        self.assertEqual(push_log.status, "CONFIGURATION_ERROR")

    # ── P10. Push test endpoint sends through the same service ──────────
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_push_test_endpoint(self):
        from unittest import mock

        from .services import PushNotificationService

        self._subscribe()
        with mock.patch.object(
            PushNotificationService, "send_to_subscription"
        ) as fake_send:
            fake_send.return_value = (True, "OK")
            response = self.client.post("/api/reminders/push/test/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "sent")
        self.assertEqual(response.data["sent"], 1)

    # ── P11. Push test endpoint reports MISSING subscription honestly ──
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_push_test_endpoint_without_subscription_is_400(self):
        # Regression: this used to crash with ValueError (3-vs-4 unpack).
        response = self.client.post("/api/reminders/push/test/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No push subscription", response.data["detail"])


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_PHONE_NUMBER="",
    VAPID_PUBLIC_KEY="",
    VAPID_PRIVATE_KEY="",
)
class ChannelSelectionTests(TestCase):
    """Per-reminder channel selection (notify_push / notify_email / notify_sms)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="channeltest",
            email="channeltest@example.com",
            password="testpass123",
            phone="+919876543210",
        )
        self.medicine = Medicine.objects.create(
            user=self.user,
            medicine_name="Aspirin",
            medicine_type="TABLET",
            dosage="100mg",
            frequency="Morning",
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )

    def _due_reminder(self, **extra):
        now = timezone.localtime()
        return Reminder.objects.create(
            user=self.user,
            medicine=self.medicine,
            reminder_date=now.date(),
            reminder_time=time_cls(now.hour, now.minute),
            status="PENDING",
            **extra,
        )

    # ── C1. SMS only: no email is sent, no push is attempted ─────────
    def test_sms_only_sends_no_email(self):
        reminder = self._due_reminder(
            notify_push=False, notify_email=False, notify_sms=True
        )
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        self.assertEqual(len(mail.outbox), 0, "Email must NOT be sent when not selected")
        self.assertFalse(
            NotificationLog.objects.filter(reminder=reminder, channel="EMAIL").exists()
        )
        self.assertFalse(
            NotificationLog.objects.filter(reminder=reminder, channel="PUSH").exists()
        )
        # SMS attempted (Twilio config is blanked -> CONFIGURATION_ERROR log)
        self.assertTrue(
            NotificationLog.objects.filter(reminder=reminder, channel="SMS").exists()
        )

    # ── C2. Email only: email sent, no push log ──────────────────────
    def test_email_only_sends_email(self):
        reminder = self._due_reminder(
            notify_push=False, notify_email=True, notify_sms=False
        )
        result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        self.assertTrue(result["email_sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(
            NotificationLog.objects.filter(reminder=reminder, channel="PUSH").exists()
        )
        self.assertFalse(
            NotificationLog.objects.filter(reminder=reminder, channel="SMS").exists()
        )

    # ── C3. Push only: no email, no SMS ──────────────────────────────
    @override_settings(
        VAPID_PUBLIC_KEY="test-public-key",
        VAPID_PRIVATE_KEY="test-private-key",
        VAPID_SUBJECT="mailto:admin@pillsync.com",
    )
    def test_push_only_no_email_no_sms(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://fcm.googleapis.com/fcm/send/sel-test",
            p256dh="B" * 87,
            auth="a" * 24,
        )
        reminder = self._due_reminder(
            notify_push=True, notify_email=False, notify_sms=False
        )
        with mock.patch("pywebpush.webpush"):
            result = NotificationService.fire_reminder(reminder)
        self.assertEqual(result["status"], "triggered")
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            NotificationLog.objects.filter(
                reminder=reminder, channel="PUSH", status="SENT"
            ).exists()
        )
        self.assertFalse(
            NotificationLog.objects.filter(reminder=reminder, channel="SMS").exists()
        )

    # ── C4. Default (legacy) reminders attempt all channels ──────────
    def test_legacy_defaults_attempt_all_channels(self):
        reminder = self._due_reminder()
        result = NotificationService.fire_reminder(reminder)        self.assertEqual(result["status"], "triggered")
        # All three channel logs exist (email SENT, sms/push config-error
        # because Twilio/VAPID are blanked in test settings).
        self.assertEqual(
            NotificationLog.objects.filter(reminder=reminder).count(), 3
        )

    # ── C5. Retry does not duplicate already-sent channels ───────────
    def test_retry_does_not_duplicate_delivered_channels(self):
        reminder = self._due_reminder()

        def failing_email_then_ok(reminder_arg, sent_channels=None):
            reminder_arg.refresh_from_db()
            if "EMAIL" in (sent_channels or set()):
                return []  # already delivered — nothing re-sent
            # Simulate: push + sms delivered, email failed this attempt.
            return [
                NotificationLog.objects.create(
                    user=self.user,
                    reminder=reminder_arg,
                    channel="PUSH",
                    recipient="1",
                    status="SENT",
                ),
                NotificationLog.objects.create(
                    user=self.user,
                    reminder=reminder_arg,
                    channel="SMS",
                    recipient="+919876543210",
                    status="SENT",
                ),
                NotificationLog.objects.create(
                    user=self.user,
                    reminder=reminder_arg,
                    channel="EMAIL",
                    recipient=self.user.email,
                    status="FAILED",
                    error_message="SMTP down",
                ),
            ]

        with mock.patch.object(
            NotificationService, "send_all", autospec=True,
            side_effect=lambda rem, sent_channels=None: failing_email_then_ok(
                rem, sent_channels
            ),
        ):
            NotificationService.fire_reminder(reminder)  # attempt 1: email fails

        # Second attempt with email now working: push/sms must be skipped.
        with mock.patch.object(NotificationService, "send_all") as fake:
            fake.return_value = [
                NotificationLog(
                    user=self.user,
                    reminder=reminder,
                    channel="EMAIL",
                    recipient=self.user.email,
                    status="SENT",
                )
            ]
            NotificationService.fire_reminder(reminder)
            # The service was asked to skip PUSH/SMS via sent_channels.
            kwargs = fake.call_args.kwargs
            self.assertIn("PUSH", kwargs["sent_channels"])
            self.assertIn("SMS", kwargs["sent_channels"])

    # ── C6. Email config check endpoint (safe, no credentials) ───────
    def test_email_config_check_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get("/api/reminders/email-config-check/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("configured", response.data)
        # Absolutely no credential values in the payload.
        self.assertNotIn("password", str(response.data).lower())

    # ── C7. Serializer accepts channel fields via the API ────────────
    def test_api_persists_channel_selection(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            "/api/reminders/",
            {
                "medicine": self.medicine.id,
                "reminder_time": "18:30:00",
                "reminder_date": timezone.localdate().isoformat(),
                "status": "PENDING",
                "notify_push": False,
                "notify_email": True,
                "notify_sms": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        reminder = Reminder.objects.get(id=response.data["id"])
        self.assertFalse(reminder.notify_push)
        self.assertTrue(reminder.notify_email)
        self.assertTrue(reminder.notify_sms)

    # ── C8. Multiple timings: every reminder gets its own channels ───
    def test_multiple_timings_each_fire_selected_channels(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        # Two reminders for the same medicine (2 times/day), email only.
        # The first time is a few minutes in the PAST (due now), the second
        # a few minutes in the FUTURE (not due yet — must be skipped by the
        # due-guard, exactly like production).
        from datetime import timedelta

        past_time = (timezone.localtime() - timedelta(minutes=5)).replace(
            microsecond=0
        ).time()
        future_time = (timezone.localtime() + timedelta(minutes=5)).replace(
            microsecond=0
        ).time()
        for t in (past_time.strftime("%H:%M:%S"), future_time.strftime("%H:%M:%S")):
            r = client.post(
                "/api/reminders/",
                {
                    "medicine": self.medicine.id,
                    "reminder_time": t,
                    "reminder_date": timezone.localdate().isoformat(),
                    "status": "PENDING",
                    "notify_push": False,
                    "notify_email": True,
                    "notify_sms": False,
                },
                format="json",
            )
            self.assertEqual(r.status_code, 201)

        # Fire each synchronously (as the scheduler catch-up does).
        fired_count = 0
        for reminder in Reminder.objects.filter(user=self.user).order_by("reminder_time"):
            result = NotificationService.fire_reminder(reminder)
            if result["status"] == "triggered":
                fired_count += 1
                self.assertTrue(result["email_sent"])

        # Exactly one was due and fired; the future one stays PENDING and
        # will fire at its own scheduled time (no early/duplicate send).
        self.assertEqual(fired_count, 1)
        self.assertEqual(len(mail.outbox), 1, "One email for the due timing")
        future_reminder = Reminder.objects.filter(user=self.user).get(
            reminder_time=future_time
        )
        self.assertEqual(future_reminder.status, "PENDING")
        self.assertFalse(future_reminder.notification_sent)
        self.assertFalse(
            NotificationLog.objects.filter(channel="PUSH").exists()
        )
        self.assertFalse(
            NotificationLog.objects.filter(channel="SMS").exists()
        )
