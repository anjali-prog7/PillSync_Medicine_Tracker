"""
Celery configuration for the PillSync project.

This module sets up the Celery application instance,
configures it with Redis as the broker/backend, and
auto-discovers tasks from all registered Django apps.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("pillsync")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related config keys
#   should have a `CELERY_` prefix in Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django app configs.
app.autodiscover_tasks()

# Celery Beat schedule: check reminders every minute
app.conf.beat_schedule = {
    "check-and-send-reminders-every-minute": {
        "task": "reminders.tasks.check_and_send_reminders",
        "schedule": 60.0,  # Every 60 seconds
    },
}

# Reminder datetimes are stored in the user's LOCAL timezone (Asia/Kolkata),
# so Celery beat must schedule in that same local timezone.
app.conf.timezone = "Asia/Kolkata"


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Simple debug task to verify Celery is running."""
    print(f"Request: {self.request!r}")
