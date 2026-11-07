from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import (
    Instance,
    InstanceFile,
    Notification,
    Run,
    RunSolution,
    TemporaryUpload,
)


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
    application.config.update(TESTING=True)
    yield application
    test_engine.dispose()


def _seed_uploads(session: Session, *, time_node_count: int = 2, distance_node_count: int = 2) -> tuple[str, str]:
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
        node_count=time_node_count,
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
        node_count=distance_node_count,
        status="valid",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    session.add_all([time_upload, distance_upload])
    session.commit()
    return time_upload.id, distance_upload.id


def test_create_instance_links_valid_uploads_and_returns_ready_status(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, distance_upload_id = _seed_uploads(session)

    response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância teste",
            "files": {
                "time_matrix": time_upload_id,
                "distance_matrix": distance_upload_id,
            },
            "node_order_confirmed": True,
            "configuration": {
                "preview": ["weighted_graph", "matrix_heatmap"],
                "result_views": ["pareto_frontier", "solutions_table"],
                "algorithm_id": "random-heuristic",
            },
        },
    )

    assert response.status_code == 201
    assert response.json["status"] == "ready"
    assert response.json["problem_type_id"] == "tsp-time-distance"
    assert response.json["name"] == "Instância teste"
    assert response.json["algorithm_id"] == "random-heuristic"

    with Session(app.extensions["paretolab_database_engine"]) as session:
        instance = session.scalar(select(Instance).where(Instance.instance_id == response.json["instance_id"]))
        files = session.scalars(select(InstanceFile).where(InstanceFile.instance_id == response.json["instance_id"])).all()

    assert instance is not None
    assert {record.role for record in files} == {"time_matrix", "distance_matrix"}
    assert instance.node_count == 2


def test_create_instance_accepts_neuro_lkh(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, distance_upload_id = _seed_uploads(session)

    response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância NeuroLKH",
            "files": {
                "time_matrix": time_upload_id,
                "distance_matrix": distance_upload_id,
            },
            "node_order_confirmed": True,
            "configuration": {
                "preview": ["weighted_graph", "matrix_heatmap"],
                "result_views": ["pareto_frontier", "solutions_table"],
                "algorithm_id": "neuro-lkh",
            },
        },
    )

    assert response.status_code == 201
    assert response.json["algorithm_id"] == "neuro-lkh"


def test_create_instance_rejects_mismatched_upload_sizes(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, _ = _seed_uploads(session, time_node_count=2, distance_node_count=3)

    response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância inválida",
            "files": {
                "time_matrix": time_upload_id,
                "distance_matrix": "upl_distance",
            },
            "node_order_confirmed": True,
            "configuration": {"algorithm_id": "random-heuristic"},
        },
    )

    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_upload_dimensions"


def test_create_instance_requires_order_confirmation(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, distance_upload_id = _seed_uploads(session)

    response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância sem confirmação",
            "files": {
                "time_matrix": time_upload_id,
                "distance_matrix": distance_upload_id,
            },
            "node_order_confirmed": False,
            "configuration": {"algorithm_id": "random-heuristic"},
        },
    )

    assert response.status_code == 422
    assert response.json["error"]["code"] == "node_order_not_confirmed"


@pytest.mark.parametrize("upload_state", ["expired", "consumed"])
def test_create_instance_rejects_expired_or_consumed_uploads(app: Flask, upload_state: str) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        time_upload_id, distance_upload_id = _seed_uploads(session)
        upload = session.get(TemporaryUpload, time_upload_id)
        if upload_state == "expired":
            upload.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            upload.consumed_at = datetime.now(UTC)
        session.commit()

    response = app.test_client().post(
        "/api/v1/instances",
        json={
            "problem_type_id": "tsp-time-distance",
            "name": "Instância com upload inválido",
            "files": {"time_matrix": time_upload_id, "distance_matrix": distance_upload_id},
            "node_order_confirmed": True,
            "configuration": {"algorithm_id": "random-heuristic"},
        },
    )

    assert response.status_code in {409, 410}
    assert response.json["error"]["code"] == (
        "upload_expired" if upload_state == "expired" else "upload_already_consumed"
    )


def test_instance_update_freezes_configuration_after_runs_and_delete_cascades(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Instance(
                instance_id="inst_manage_1",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="Original",
                status="ready",
                configuration={"algorithm_id": "random-heuristic", "preview": [], "result_views": []},
                node_count=3,
            )
        )
        session.commit()

    client = app.test_client()
    rename_response = client.patch("/api/v1/instances/inst_manage_1", json={"name": "Renomeada"})
    assert rename_response.status_code == 200
    assert rename_response.json["name"] == "Renomeada"

    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Run(
                run_id="run_manage_1",
                instance_id="inst_manage_1",
                algorithm_id="random-heuristic",
                status="running",
                parameters={"iterations": 2, "seed": 1},
                progress={"completed": 1, "total": 2, "percent": 50},
                idempotency_key="manage-1",
            )
        )
        session.add(
            RunSolution(
                solution_id="sol_manage_1",
                run_id="run_manage_1",
                instance_id="inst_manage_1",
                objective_values={"time": 1.0, "distance": 2.0},
                route=[1, 2, 3, 1],
                dominance="non_dominated",
            )
        )
        session.add(
            Notification(
                notification_id="notif_manage_1",
                instance_id="inst_manage_1",
                run_id="run_manage_1",
                title="Execução",
                message="Em execução",
                is_read=False,
            )
        )
        session.commit()

    config_response = client.patch(
        "/api/v1/instances/inst_manage_1",
        json={"configuration": {"algorithm_id": "random-heuristic", "preview": [], "result_views": []}},
    )
    assert config_response.status_code == 409
    assert client.delete("/api/v1/instances/inst_manage_1").status_code == 409

    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.get(Run, "run_manage_1").status = "completed"
        session.commit()

    delete_response = client.delete("/api/v1/instances/inst_manage_1")
    assert delete_response.status_code == 202
    with Session(app.extensions["paretolab_database_engine"]) as session:
        assert session.get(Instance, "inst_manage_1") is None
        assert session.get(Run, "run_manage_1") is None
        assert session.get(RunSolution, "sol_manage_1") is None
        assert session.get(Notification, "notif_manage_1") is None


def test_instance_list_rejects_invalid_pagination(app: Flask) -> None:
    response = app.test_client().get("/api/v1/instances?limit=-1")
    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_pagination"
