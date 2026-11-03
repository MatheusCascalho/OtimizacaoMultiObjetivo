from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import CityLayout, Instance, Notification, Run, RunSolution


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


def test_results_and_notifications_are_exposed_for_completed_run(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Instance(
                instance_id="inst_results_1",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="Instância resultados",
                status="ready",
                configuration={"algorithm_id": "random-heuristic"},
                node_count=3,
            )
        )
        session.add(
            Run(
                run_id="run_results_1",
                instance_id="inst_results_1",
                algorithm_id="random-heuristic",
                status="completed",
                parameters={"iterations": 5},
                progress={"completed": 5, "total": 5, "percent": 100},
                created_at=datetime(2026, 11, 2, tzinfo=UTC),
                updated_at=datetime(2026, 11, 2, tzinfo=UTC),
            )
        )
        session.add(
            RunSolution(
                solution_id="sol_1",
                run_id="run_results_1",
                instance_id="inst_results_1",
                objective_values={"time": 3.5, "distance": 8.0},
                route=[1, 2, 3, 1],
                dominance="non_dominated",
                created_at=datetime(2026, 11, 2, tzinfo=UTC),
            )
        )
        session.add_all(
            [
                CityLayout(id="layout_1", instance_id="inst_results_1", city_index=0, x=10, y=20),
                CityLayout(id="layout_2", instance_id="inst_results_1", city_index=1, x=30, y=40),
                CityLayout(id="layout_3", instance_id="inst_results_1", city_index=2, x=50, y=60),
            ]
        )
        session.add(
            Notification(
                notification_id="notif_1",
                instance_id="inst_results_1",
                run_id="run_results_1",
                title="Execução concluída",
                message="A execução da instância foi concluída.",
                is_read=False,
                created_at=datetime(2026, 11, 2, tzinfo=UTC),
            )
        )
        session.commit()

    client = app.test_client()
    results_response = client.get("/api/v1/runs/run_results_1/results")
    assert results_response.status_code == 200
    assert results_response.json["run_id"] == "run_results_1"
    assert len(results_response.json["solutions"]) == 1
    assert results_response.json["solutions"][0]["dominance"] == "non_dominated"
    assert results_response.json["total"] == 1
    assert results_response.json["non_dominated"] == 1

    solution_response = client.get("/api/v1/runs/run_results_1/solutions/sol_1")
    assert solution_response.status_code == 200
    assert solution_response.json["objective_values"]["time"] == 3.5

    graph_response = client.get("/api/v1/runs/run_results_1/solutions/sol_1/graph")
    assert graph_response.status_code == 200
    assert len(graph_response.json["edges"]) == 3
    assert graph_response.json["nodes"] == [
        {"id": 1, "label": "1", "x": 10.0, "y": 20.0},
        {"id": 2, "label": "2", "x": 30.0, "y": 40.0},
        {"id": 3, "label": "3", "x": 50.0, "y": 60.0},
    ]

    csv_response = client.get("/api/v1/runs/run_results_1/solutions/sol_1/route.csv")
    assert csv_response.status_code == 200
    assert "sequence,city_id" in csv_response.get_data(as_text=True)

    notifications_response = client.get("/api/v1/notifications")
    assert notifications_response.status_code == 200
    assert notifications_response.json["notifications"][0]["notification_id"] == "notif_1"

    mark_response = client.patch("/api/v1/notifications/notif_1")
    assert mark_response.status_code == 200
    assert mark_response.json["is_read"] is True


def test_results_are_blocked_before_run_completes(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Instance(
                instance_id="inst_results_2",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="Instância pendente",
                status="ready",
                configuration={"algorithm_id": "random-heuristic"},
                node_count=2,
            )
        )
        session.add(
            Run(
                run_id="run_results_2",
                instance_id="inst_results_2",
                algorithm_id="random-heuristic",
                status="running",
                parameters={"iterations": 10},
                progress={"completed": 3, "total": 10, "percent": 30},
                created_at=datetime(2026, 11, 2, tzinfo=UTC),
                updated_at=datetime(2026, 11, 2, tzinfo=UTC),
            )
        )
        session.commit()

    response = app.test_client().get("/api/v1/runs/run_results_2/results")

    assert response.status_code == 409
    assert response.json["error"]["code"] == "run_not_completed"
