from django.db import models
from accounts.models import User
from medicines.models import Medicine


class Reminder(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("TRIGGERED", "Triggered"),
        ("TAKEN", "Taken"),
        ("MISSED", "Missed"),
        ("SNOOZED", "Snoozed"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reminders"
    )

    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name="reminders"
    )

    reminder_time = models.TimeField()

    reminder_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    notification_sent = models.BooleanField(default=False)

    is_recurring = models.BooleanField(default=False)

    recurring_interval = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Daily, Weekly, Monthly"
    )

    snoozed_until = models.DateTimeField(
        blank=True,
        null=True,
        help_text="If snoozed, the time until which the reminder is snoozed"
    )

    retry_count = models.PositiveIntegerField(default=0)

    # ── Notification channel selection (PillSync supports exactly 3) ──
    # Previously every reminder attempted every configured channel; these
    # fields let the user choose Push / Email / SMS per reminder. All default
    # to True so EXISTING rows/API calls keep the legacy behaviour (all
    # channels attempted). The frontend now sends explicit selections.
    notify_push = models.BooleanField(default=True)

    notify_email = models.BooleanField(default=True)

    notify_sms = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.medicine.medicine_name} - {self.reminder_time}"


class PushSubscription(models.Model):
    """
    A browser Web Push subscription for a user.

    Created by the frontend after Notification.requestPermission() and
    pushManager.subscribe() succeed. One user may have several (multiple
    browsers/devices); all are attempted when a reminder fires.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )

    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=100)
    auth = models.CharField(max_length=100)

    # Which browser/device created this subscription (informational).
    user_agent = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PushSubscription user={self.user_id} {self.endpoint[:60]}..."


class NotificationLog(models.Model):

    CHANNEL_CHOICES = (
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
        ("PUSH", "Push"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
        ("CONFIGURATION_ERROR", "Configuration Error"),
        ("SKIPPED", "Skipped"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_logs"
    )

    reminder = models.ForeignKey(
        Reminder,
        on_delete=models.CASCADE,
        related_name="notification_logs"
    )

    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES
    )

    recipient = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Email address, phone number, or device token"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    sent_at = models.DateTimeField(
        blank=True,
        null=True
    )

    error_message = models.TextField(
        blank=True,
        null=True
    )

    retry_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "reminder"]),
            models.Index(fields=["status"]),
            models.Index(fields=["channel"]),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} - {self.reminder} - {self.get_status_display()}"
