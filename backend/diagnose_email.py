"""
Safe, real Django email diagnostic script (standalone, no interactive shell).

Uses the EXACT same email configuration as the application (settings.py).
Prints only PRESENT/MISSING and connection-level info - NEVER secret values.

Run (from backend/):
  venv/Scripts/python.exe diagnose_email.py
"""
import os
import sys
import socket
import smtplib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.mail import get_connection, send_mail  # noqa: E402


def present(v):
    return "PRESENT" if v else "MISSING"


print("=" * 60)
print("1. DJANGO EMAIL CONFIG (values never printed)")
print("=" * 60)
print(f"EMAIL_BACKEND        = {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST           = {settings.EMAIL_HOST}")
print(f"EMAIL_PORT           = {settings.EMAIL_PORT}")
print(f"EMAIL_HOST_USER      = {present(settings.EMAIL_HOST_USER)}")
print(f"EMAIL_HOST_PASSWORD  = {present(settings.EMAIL_HOST_PASSWORD)}")
print(f"EMAIL_USE_TLS        = {settings.EMAIL_USE_TLS}")
print(f"EMAIL_USE_SSL        = {getattr(settings, 'EMAIL_USE_SSL', False)}")
print(f"DEFAULT_FROM_EMAIL   = {settings.DEFAULT_FROM_EMAIL}")
print(f"host == from match   = {settings.EMAIL_HOST_USER == settings.DEFAULT_FROM_EMAIL}")
sys.stdout.flush()

print()
print("=" * 60)
print("2. DNS RESOLUTION")
print("=" * 60)
try:
    ip = socket.gethostbyname(settings.EMAIL_HOST)
    print(f"OK  {settings.EMAIL_HOST} -> {ip}")
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}")
    sys.exit(1)
sys.stdout.flush()

print()
print("=" * 60)
print("3. RAW SMTP CONNECT + STARTTLS + AUTH (real connection)")
print("=" * 60)
print(f"Connecting to {settings.EMAIL_HOST}:{settings.EMAIL_PORT} (timeout 25s) ...")
sys.stdout.flush()
try:
    conn = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        fail_silently=False,
        timeout=25,
    )
    conn.open()
    print("OK  SMTP connection opened; STARTTLS + AUTH succeeded")
    conn.close()
    print("OK  Connection closed cleanly")
    print(">>> SMTP CONNECT + TLS + AUTH: ALL PASSED <<<")
except smtplib.SMTPAuthenticationError as e:
    print(f"FAIL SMTPAuthenticationError [{e.smtp_code}] {str(e).splitlines()[0][:160]}")
    print(">>> Gmail requires a 16-char App Password (not the account password),")
    print(">>> and EMAIL_HOST_USER must be the full gmail address.")
    sys.exit(2)
except (smtplib.SMTPException, OSError) as e:
    print(f"FAIL {type(e).__name__}: {str(e)[:200]}")
    sys.exit(3)
sys.stdout.flush()

print()
print("=" * 60)
print("4. REAL SEND TEST (Django -> Gmail SMTP -> own inbox)")
print("=" * 60)
recipient = settings.DEFAULT_FROM_EMAIL  # send to the owner's own address
masked = recipient[:2] + "***@" + recipient.split("@")[1] if "@" in recipient else "<invalid>"
print(f"Sending test mail to {masked} ...")
sys.stdout.flush()
try:
    n = send_mail(
        subject="PillSync email diagnostic - real send test",
        message="If you received this, Django -> Gmail SMTP -> inbox works end to end.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )
    print(f"OK  send_mail returned {n} (1 = accepted by Gmail for delivery)")
    print(">>> REAL EMAIL SEND: PASSED - check the inbox (and Spam).")
except smtplib.SMTPException as e:
    print(f"FAIL {type(e).__name__} [{getattr(e, 'smtp_code', '-')}] {str(e).splitlines()[0][:200]}")
    sys.exit(4)
except OSError as e:
    print(f"FAIL {type(e).__name__}: {str(e)[:200]}")
    sys.exit(5)
sys.stdout.flush()
print()
print("DIAGNOSTIC COMPLETE")
