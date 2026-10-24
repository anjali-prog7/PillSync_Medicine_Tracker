"""PillSync configuration package."""

# Make Celery import optional so the backend can start without Celery installed.
try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:
    # Celery (and redis) may not be installed in dev/test environments
    celery_app = None
    __all__ = ()
