from collections.abc import Iterator

import pytest
from flask import Flask
from sqlalchemy.exc import OperationalError

from api import create_app
from api.routes import health
from api.settings import Settings


def dependency_available(*dependencies: object) -> None:
    assert dependencies


@pytest.fixture
def app() -> Iterator[Flask]:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:password@localhost/paretolab",
        celery_broker_url="redis://localhost:6379/0",
        s3_endpoint_url="http://localhost:9000",
        s3_bucket="paretolab-local",
        s3_access_key="local-access",
        s3_secret_key="local-secret",
    )
    application = create_app(settings)
    application.config.update(TESTING=True)
    yield application
    application.extensions["paretolab_database_engine"].dispose()


def test_liveness_does_not_depend_on_external_services(app: Flask) -> None:
    client = app.test_client()

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json == {"status": "live"}


def test_cors_allows_loopback_frontend_without_credentials(app: Flask) -> None:
    response = app.test_client().get(
        "/health/live",
        headers={"Origin": "http://127.0.0.1:8080"},
    )

    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8080"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_cors_does_not_allow_remote_origins(app: Flask) -> None:
    response = app.test_client().get(
        "/health/live",
        headers={"Origin": "https://example.com"},
    )

    assert "Access-Control-Allow-Origin" not in response.headers


def test_readiness_reports_available_dependencies(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "_check_database", dependency_available)
    monkeypatch.setattr(health, "_check_broker", dependency_available)
    monkeypatch.setattr(health, "_check_object_storage", dependency_available)

    response = app.test_client().get("/health/ready")

    assert response.status_code == 200
    assert response.json == {
        "status": "ready",
        "dependencies": {
            "database": "available",
            "broker": "available",
            "object_storage": "available",
        },
    }


def test_readiness_returns_service_unavailable_if_database_is_down(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def database_unavailable(_: object) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("unavailable"))

    monkeypatch.setattr(health, "_check_database", database_unavailable)
    monkeypatch.setattr(health, "_check_broker", dependency_available)
    monkeypatch.setattr(health, "_check_object_storage", dependency_available)

    response = app.test_client().get("/health/ready")

    assert response.status_code == 503
    assert response.json["status"] == "not_ready"
    assert response.json["dependencies"]["database"] == "unavailable"
