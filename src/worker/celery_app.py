from celery import Celery

from api.settings import Settings


def create_celery_app(settings: Settings) -> Celery:
    celery_app = Celery(
        "paretolab",
        broker=settings.celery_broker_url,
        include=["worker.tasks"],
    )
    celery_app.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        enable_utc=True,
        result_backend=None,
        task_acks_late=True,
        task_serializer="json",
        timezone="UTC",
        worker_prefetch_multiplier=1,
        beat_schedule={
            "cleanup-expired-uploads": {
                "task": "worker.cleanup_expired_uploads",
                "schedule": 300.0,
            }
        },
    )
    return celery_app
