from celery import shared_task


@shared_task(name="worker.ping")
def ping_worker() -> str:
    return "pong"
