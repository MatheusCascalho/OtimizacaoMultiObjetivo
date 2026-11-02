from collections.abc import Iterator
from hashlib import sha256
from io import BytesIO

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import TemporaryUpload


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        assert content_type == "text/csv"
        assert metadata["sha256"] == sha256(content).hexdigest()
        self.objects[key] = content

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


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
        max_upload_bytes=10,
    )
    application = create_app(settings)
    original_engine = application.extensions["paretolab_database_engine"]
    original_engine.dispose()
    test_engine = create_engine("sqlite://")
    Base.metadata.create_all(test_engine)
    application.extensions["paretolab_database_engine"] = test_engine
    application.extensions["paretolab_object_storage"] = FakeObjectStorage()
    application.config.update(TESTING=True)
    yield application
    test_engine.dispose()


def test_upload_valid_csv_stores_object_and_persists_metadata(app: Flask) -> None:
    content = b"0,1\n2,0\n"
    response = app.test_client().post(
        "/api/v1/uploads",
        data={
            "problem_type_id": "tsp-time-distance",
            "role": "time_matrix",
            "file": (BytesIO(content), "time.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.json["role"] == "time_matrix"
    assert response.json["size_bytes"] == len(content)
    assert response.json["sha256"] == sha256(content).hexdigest()
    assert response.json["node_count"] == 2
    assert response.json["status"] == "valid"

    with Session(app.extensions["paretolab_database_engine"]) as session:
        upload = session.scalar(
            select(TemporaryUpload).where(TemporaryUpload.id == response.json["upload_id"])
        )
    assert upload is not None
    assert upload.catalog_version == "1.0.0"
    assert upload.consumed_at is None
    assert upload.object_key.startswith("temporary-uploads/")
    assert upload.original_filename == "time.csv"
    assert upload.object_key in app.extensions["paretolab_object_storage"].objects


def test_upload_rejects_invalid_matrix_without_storing_object(app: Flask) -> None:
    response = app.test_client().post(
        "/api/v1/uploads",
        data={
            "problem_type_id": "tsp-time-distance",
            "role": "distance_matrix",
            "file": (BytesIO(b"0,-1\n2,0\n"), "distance.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_matrix_value"
    assert response.json["error"]["details"] == [
        {"file": "distance.csv", "row": 1, "column": 2}
    ]
    assert app.extensions["paretolab_object_storage"].objects == {}


def test_upload_rejects_file_over_configured_limit(app: Flask) -> None:
    response = app.test_client().post(
        "/api/v1/uploads",
        data={
            "problem_type_id": "tsp-time-distance",
            "role": "time_matrix",
            "file": (BytesIO(b"0,1234\n2,0\n"), "time.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.json["error"]["code"] == "file_too_large"
    assert app.extensions["paretolab_object_storage"].objects == {}


def test_upload_rejects_role_not_in_problem_catalog(app: Flask) -> None:
    response = app.test_client().post(
        "/api/v1/uploads",
        data={
            "problem_type_id": "tsp-time-distance",
            "role": "route_file",
            "file": (BytesIO(b"0,1\n2,0\n"), "route.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_file_role"
    assert app.extensions["paretolab_object_storage"].objects == {}