from django.db import migrations, models


class Migration(migrations.Migration):
    """
    SAFE, additive-only migration.

    Adds three boolean columns to the existing Reminder table:
        notify_push  (default True)
        notify_email (default True)
        notify_sms   (default False)

    - No existing rows are modified, deleted or reset.
    - Existing medicines, reminders and notification logs are untouched.
    - All three default to True so existing reminders keep attempting every
      configured channel exactly as before (legacy behaviour preserved).
    """

    dependencies = [
        ("reminders", "0003_pushsubscription_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="notify_push",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="reminder",
            name="notify_email",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="reminder",
            name="notify_sms",
            field=models.BooleanField(default=True),
        ),
    ]
