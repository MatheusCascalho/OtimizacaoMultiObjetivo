from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import CityLayout, TemporaryUpload


class FakeObjectStorage:
    def __init__(self, data: dict[str, bytes]) -> None:
        self.data = data

    def get(self, key: str) -> bytes:
        return self.data[key]


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
    test_engine = create_engine("sqlite://")
    Base.metadata.create_all(test_engine)
    application.extensions["paretolab_database_engine"] = test_engine
    application.extensions["paretolab_object_storage"] = FakeObjectStorage(
        {
            "temporary-uploads/time": b"0,2\n5,0\n",
            "temporary-uploads/distance": b"0,8\n4,0\n",
        }
    )
    application.config.update(TESTING=True)
    yield application
    test_engine.dispose()


def _seed_uploads(session: Session) -> tuple[str, str]:
    now = datetime.now(UTC)
    time_upload = TemporaryUpload(
        id="upl_time",
        problem_type_id="tsp-time-distance",
        catalog_version="1.0.0",
        role="time_matrix",
        original_filename="time.csv",
        object_key="temporary-uploads/time",
        size_bytes=64,
        sha256="a" * 64,
        content_type="text/csv",
        node_count=2,
        status="valid",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    distance_upload = TemporaryUpload(
        id="upl_distance",
        problem_type_id="tsp-time-distance",
        catalog_version="1.0.0",
        role="distance_matrix",
        original_filename="distance.csv",
        object_key="temporary-uploads/distance",
        size_bytes=64,
        sha256="b" * 64,
        content_type="text/csv",
        node_count=2,
        status="valid",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    session.add_all([time_upload, distance_upload])
    session.commit()
    return time_upload.id, distance_upload.id


def test_analysis_input_matrix_and_graph_are_available_for_instance(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, distance_upload_id = _seed_uploads(session)

    create_response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância análise",
            "files": {"time_matrix": time_upload_id, "distance_matrix": distance_upload_id},
            "node_order_confirmed": True,
            "configuration": {"algorithm_id": "random-heuristic"},
        },
    )
    instance_id = create_response.json["instance_id"]

    matrix_response = app.test_client().get(
        f"/api/v1/instances/{instance_id}/analysis/input/matrix?objective=time"
    )
    graph_response = app.test_client().get(
        f"/api/v1/instances/{instance_id}/analysis/input/graph?objective=time&neighbors_per_city=20"
    )

    assert matrix_response.status_code == 200
    assert matrix_response.json["objective"]["id"] == "time"
    assert matrix_response.json["matrix"] == [[0.0, 2.0], [5.0, 0.0]]
    assert len(matrix_response.json["nodes"]) == 2

    assert graph_response.status_code == 200
    assert graph_response.json["neighbors_per_city"]["requested"] == 20
    assert graph_response.json["neighbors_per_city"]["effective"] == 1
    assert len(graph_response.json["edges"]) == 2
    assert {edge["source"] for edge in graph_response.json["edges"]} == {1, 2}

    default_graph_response = app.test_client().get(
        f"/api/v1/instances/{instance_id}/analysis/input/graph?objective=time"
    )
    assert default_graph_response.status_code == 200
    assert default_graph_response.json["neighbors_per_city"] == {"requested": 20, "effective": 1}

    with Session(app.extensions["paretolab_database_engine"]) as session:
        layouts = session.scalars(select(CityLayout).where(CityLayout.instance_id == instance_id)).all()
    assert len(layouts) == 2
    assert all(layout.x is not None and layout.y is not None for layout in layouts)
