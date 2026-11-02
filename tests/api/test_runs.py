from collections.abc import Iterator

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import Instance, Run


class FakeCelery:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_task(self, name: str, kwargs: dict | None = None, **_) -> dict:
        self.sent.append({"name": name, "kwargs": kwargs or {}})
        return {"id": "celery-task-id"}


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
    application.extensions["paretolab_celery_app"] = FakeCelery()
    application.config.update(TESTING=True)
    yield application
    test_engine.dispose()


def test_run_creation_and_cancel_cycle(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Instance(
                instance_id="inst_runs_1",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="Instância de execução",
                status="ready",
                configuration={"algorithm_id": "random-heuristic"},
                node_count=2,
            )
        )
        session.commit()

    client = app.test_client()
    create_response = client.post(
        "/api/v1/instances/inst_runs_1/runs",
        headers={"Idempotency-Key": "idem-001"},
        json={"parameters": {"iterations": 25, "seed": 7}},
    )

    assert create_response.status_code == 202
    run_id = create_response.json["run_id"]
    assert create_response.json["status"] == "queued"
    assert create_response.json["status_url"] == f"/api/v1/runs/{run_id}"

    list_response = client.get("/api/v1/instances/inst_runs_1/runs")
    assert list_response.status_code == 200
    assert list_response.json["runs"][0]["run_id"] == run_id

    status_response = client.get(f"/api/v1/runs/{run_id}")
    assert status_response.status_code == 200
    assert status_response.json["instance_id"] == "inst_runs_1"
    assert status_response.json["status"] == "queued"

    cancel_response = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancel_response.status_code == 202
    assert cancel_response.json["status"] == "cancel_requested"

    with Session(app.extensions["paretolab_database_engine"]) as session:
        run = session.scalar(select(Run).where(Run.run_id == run_id))
    assert run is not None
    assert run.status == "cancel_requested"
    assert run.idempotency_key == "idem-001"
