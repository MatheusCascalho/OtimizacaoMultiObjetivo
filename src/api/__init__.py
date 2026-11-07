from urllib.parse import urlparse

from flask import Flask, request
from sqlalchemy.engine import Engine

from api.routes.emission import emission_blueprint
from api.routes.health import health_blueprint
from api.routes.instances import instances_blueprint
from api.routes.notifications import notifications_blueprint
from api.routes.problem_types import problem_types_blueprint
from api.routes.robustness import robustness_blueprint
from api.routes.runs import runs_blueprint
from api.routes.uploads import uploads_blueprint
from api.settings import Settings
from infrastructure.catalog.json import JsonProblemTypeCatalog
from infrastructure.object_storage.s3.storage import S3ObjectStorage
from infrastructure.object_storage.s3.client import create_s3_client
from infrastructure.persistence.postgres.database import create_engine
from worker.celery_app import create_celery_app


def create_app(settings: Settings | None = None) -> Flask:
    application_settings = settings or Settings()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=application_settings.max_upload_bytes + 64 * 1024)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin:
            parsed_origin = urlparse(origin)
            if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Idempotency-Key"
                response.vary.add("Origin")
        return response

    engine: Engine = create_engine(application_settings)
    celery_app = create_celery_app(application_settings)
    s3_client = create_s3_client(application_settings)

    app.extensions["paretolab_settings"] = application_settings
    app.extensions["paretolab_database_engine"] = engine
    app.extensions["paretolab_celery_app"] = celery_app
    app.extensions["paretolab_s3_client"] = s3_client
    app.extensions["paretolab_object_storage"] = S3ObjectStorage(
        s3_client,
        application_settings.s3_bucket,
    )
    app.extensions["paretolab_catalog"] = JsonProblemTypeCatalog()
    app.register_blueprint(health_blueprint)
    app.register_blueprint(problem_types_blueprint)
    app.register_blueprint(uploads_blueprint)
    app.register_blueprint(instances_blueprint)
    app.register_blueprint(runs_blueprint)
    app.register_blueprint(emission_blueprint)
    app.register_blueprint(robustness_blueprint)
    app.register_blueprint(notifications_blueprint)

    return app


__all__ = ["create_app"]
