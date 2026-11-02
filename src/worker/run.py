from api.settings import Settings
from worker.celery_app import create_celery_app


def main() -> None:
    celery_app = create_celery_app(Settings())
    celery_app.worker_main(["worker", "--loglevel=INFO"])


if __name__ == "__main__":
    main()
