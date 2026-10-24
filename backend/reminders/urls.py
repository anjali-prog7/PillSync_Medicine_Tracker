from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReminderViewSet,
    NotificationLogViewSet,
    PushSubscriptionView,
    PushVapidKeyView,
    PushTestView,
    EmailConfigCheckView,
)

router = DefaultRouter()

# IMPORTANT: register "notification-logs" BEFORE the empty-prefix
# ReminderViewSet. The ReminderViewSet detail route is
# ^(?P<pk>[^/.]+)/$ — with an empty prefix it would otherwise capture
# "notification-logs" as a pk and return 404 for
# /api/reminders/notification-logs/.
router.register(
    r"notification-logs", NotificationLogViewSet, basename="notification-log"
)
router.register(r"", ReminderViewSet, basename="reminder")

urlpatterns = [
    # Web Push subscription endpoints (registered BEFORE the router include
    # so the empty-prefix ReminderViewSet cannot shadow them).
    path("push/vapid-key/", PushVapidKeyView.as_view(), name="push-vapid-key"),
    path("push/subscribe/", PushSubscriptionView.as_view(), name="push-subscribe"),
    path("push/test/", PushTestView.as_view(), name="push-test"),
    # Safe SMTP-config presence check (no credentials ever returned).
    path("email-config-check/", EmailConfigCheckView.as_view(), name="email-config-check"),
    path("", include(router.urls)),
]
