from flask import Flask
from sqlalchemy.engine import Engine

from api.routes.health import health_blueprint
from api.settings import Settings
from infrastructure.object_storage.s3.client import create_s3_client
from infrastructure.persistence.postgres.database import create_engine
from worker.celery_app import create_celery_app


def create_app(settings: Settings | None = None) -> Flask:
    application_settings = settings or Settings()
    app = Flask(__name__)
    engine: Engine = create_engine(application_settings)
    celery_app = create_celery_app(application_settings)
    s3_client = create_s3_client(application_settings)

    app.extensions["paretolab_settings"] = application_settings
    app.extensions["paretolab_database_engine"] = engine
    app.extensions["paretolab_celery_app"] = celery_app
    app.extensions["paretolab_s3_client"] = s3_client
    app.register_blueprint(health_blueprint)

    return app


__all__ = ["create_app"]
