import re
from datetime import time as time_cls

from rest_framework import serializers

from .models import Reminder, NotificationLog, PushSubscription


class FlexibleTimeField(serializers.TimeField):
    """
    Accepts BOTH 24-hour ("17:32") and 12-hour ("05:32 PM", "5:32PM")
    time strings and always stores the 24-hour value.

    This guarantees the PM/AM the user selected is never lost, so emails
    and notifications always display the exact chosen time.
    """

    def to_internal_value(self, value):
        if isinstance(value, str):
            match = re.match(
                r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)?\s*$",
                value.strip().upper(),
            )
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                ampm = match.group(3)
                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return time_cls(hour, minute)
        return super().to_internal_value(value)


class ReminderSerializer(serializers.ModelSerializer):

    reminder_time = FlexibleTimeField()

    class Meta:
        model = Reminder
        fields = "__all__"
        read_only_fields = ["user"]


class NotificationLogSerializer(serializers.ModelSerializer):

    reminder_details = serializers.SerializerMethodField()

    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "user",
            "reminder",
            "channel",
            "recipient",
            "status",
            "sent_at",
            "error_message",
            "retry_count",
            "created_at",
            "reminder_details",
        ]
        read_only_fields = ["user"]

    def get_reminder_details(self, obj):
        if obj.reminder:
            return {
                "id": obj.reminder.id,
                "medicine": obj.reminder.medicine.medicine_name,
                "time": obj.reminder.reminder_time.strftime("%I:%M %p"),
                "date": obj.reminder.reminder_date.isoformat(),
                "status": obj.reminder.status,
            }
        return None


class PushSubscriptionSerializer(serializers.Serializer):
    """
    Validates a browser PushSubscription JSON object and upserts it for the
    logged-in user.

    Expected payload (exactly what subscription.toJSON() gives the frontend):
    {
      "endpoint": "https://fcm.googleapis.com/fcm/send/...",
      "keys": { "p256dh": "...", "auth": "..." }
    }
    """

    endpoint = serializers.URLField(max_length=500)
    keys = serializers.DictField(child=serializers.CharField())
    user_agent = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    def validate_keys(self, value):
        p256dh = value.get("p256dh")
        auth = value.get("auth")
        if not p256dh or not auth:
            raise serializers.ValidationError(
                "PushSubscription keys must include both 'p256dh' and 'auth'."
            )
        if len(p256dh) > 100 or len(auth) > 100:
            raise serializers.ValidationError(
                "Push subscription key values are too long to be valid."
            )
        return value

    def create(self, validated_data):
        keys = validated_data["keys"]
        request = self.context["request"]
        sub, created = PushSubscription.objects.update_or_create(
            endpoint=validated_data["endpoint"],
            defaults={
                "user": request.user,
                "p256dh": keys["p256dh"],
                "auth": keys["auth"],
                "user_agent": validated_data.get("user_agent", "")[:255],
            },
        )
        return sub
