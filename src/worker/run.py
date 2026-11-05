import os

from api.settings import Settings
from worker.celery_app import create_celery_app


def main() -> None:
    celery_app = create_celery_app(Settings())
    args = ["worker", "--loglevel=INFO"]
    pool = os.environ.get("CELERY_WORKER_POOL")
    if pool:
        args.extend(["--pool", pool])
    concurrency = os.environ.get("CELERY_WORKER_CONCURRENCY")
    if concurrency:
        args.extend(["--concurrency", concurrency])
    celery_app.worker_main(args)


if __name__ == "__main__":
    main()
