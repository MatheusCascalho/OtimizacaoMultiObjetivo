from api.settings import Settings
from worker.celery_app import create_celery_app


def main() -> None:
    celery_app = create_celery_app(Settings())
    if not celery_app.control.ping(timeout=3):
        raise SystemExit("No Celery worker responded to ping")


if __name__ == "__main__":
    main()
