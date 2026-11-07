import logging
from collections.abc import Callable
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError
from celery import Celery
from flask import Blueprint, current_app, jsonify
from kombu.exceptions import OperationalError as BrokerOperationalError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine


health_blueprint = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


class S3BucketClient(Protocol):
    def head_bucket(self, *, Bucket: str) -> object: ...


def _check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _check_broker(celery_app: Celery) -> None:
    with celery_app.connection_for_read() as connection:
        connection.ensure_connection(max_retries=0)


def _check_object_storage(s3_client: S3BucketClient, bucket: str) -> None:
    s3_client.head_bucket(Bucket=bucket)


@health_blueprint.get("/health/live")
def live():
    return jsonify({"status": "live"}), 200


@health_blueprint.get("/health/ready")
def ready():
    dependencies = {
        "database": _probe(
            "database",
            _check_database,
            current_app.extensions["paretolab_database_engine"],
            exceptions=(SQLAlchemyError,),
        ),
        "broker": _probe(
            "broker",
            _check_broker,
            current_app.extensions["paretolab_celery_app"],
            exceptions=(BrokerOperationalError,),
        ),
        "object_storage": _probe(
            "object_storage",
            _check_object_storage,
            current_app.extensions["paretolab_s3_client"],
            current_app.extensions["paretolab_settings"].s3_bucket,
            exceptions=(BotoCoreError, ClientError),
        ),
    }
    is_ready = all(dependencies.values())
    return (
        jsonify(
            {
                "status": "ready" if is_ready else "not_ready",
                "dependencies": {
                    name: "available" if available else "unavailable"
                    for name, available in dependencies.items()
                },
            }
        ),
        200 if is_ready else 503,
    )


def _probe(
    dependency: str,
    check: Callable[..., object],
    *args: object,
    exceptions: tuple[type[Exception], ...],
) -> bool:
    try:
        check(*args)
    except exceptions:
        logger.exception("Readiness check failed for %s", dependency)
        return False
    return True
