from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import Instance, Run, RunSolution
from multiobjective_algorithms import analyze_robustness


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


def _matrices() -> tuple[list[list[float]], list[list[float]]]:
    time = [[0.0, 2.5, 0.0, 1.5], [1.5, 0.0, 2.5, 0.0], [0.0, 1.5, 0.0, 2.5], [2.5, 0.0, 1.5, 0.0]]
    distance = [[0.0, 1.0, 0.0, 2.0], [2.0, 0.0, 1.0, 0.0], [0.0, 2.0, 0.0, 1.0], [1.0, 0.0, 2.0, 0.0]]
    return time, distance


def _add_instance(session: Session, *, run_status: str = "completed") -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    session.add(
        Instance(
            instance_id="inst_robust",
            problem_type_id="tsp-time-distance",
            catalog_version="1.0.0",
            name="Instância robustez",
            status="completed",
            configuration={"algorithm_id": "random-heuristic"},
            node_count=4,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        Run(
            run_id="run_robust",
            instance_id="inst_robust",
            algorithm_id="random-heuristic",
            status=run_status,
            parameters={"iterations": 5},
            progress={"completed": 5, "total": 5, "percent": 100},
            created_at=now,
            updated_at=now,
        )
    )
    routes = {
        "sol_near": ([1, 2, 3, 4, 1], {"time": 9.1, "distance": 4.0}),
        "sol_near_dup": ([1, 2, 3, 4, 1], {"time": 10.0, "distance": 4.0}),
        "sol_far": ([1, 4, 3, 2, 1], {"time": 6.0, "distance": 8.0}),
        "sol_dominated": ([1, 2, 4, 3, 1], {"time": 20.0, "distance": 20.0}),
    }
    for solution_id, (route, objectives) in routes.items():
        session.add(
            RunSolution(
                solution_id=solution_id,
                run_id="run_robust",
                instance_id="inst_robust",
                objective_values=objectives,
                route=route,
                dominance="non_dominated",
                round_index=1,
                created_at=now,
            )
        )
    session.commit()


def test_robustness_evaluates_the_approximate_front_without_reoptimizing(app: Flask, monkeypatch) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session)
    monkeypatch.setattr("api.routes.robustness.load_matrices", lambda instance_id: _matrices())

    response = app.test_client().post(
        "/api/v1/instances/inst_robust/robustness",
        json={"scenarios": 24, "cv": 0, "rho": 0, "rho0": 0, "seed": 4, "include_sensitivity": False},
    )

    assert response.status_code == 200
    body = response.json
    assert body["run_id"] == "run_robust"
    assert body["solution_count"] == 2
    assert [item["solution_id"] for item in body["solutions"]] == ["sol_near", "sol_far"]
    assert [item["label"] for item in body["solutions"]] == ["S1", "S2"]
    assert body["solutions"][0]["distance"] == pytest.approx(4)
    assert body["solutions"][0]["nominal_time"] == pytest.approx(10)
    assert body["solutions"][0]["co2_kg"] is not None
    assert body["solutions"][0]["total_speed_emission_factor"] is not None
    assert body["solutions"][0]["mean"] == pytest.approx(10)
    assert body["solutions"][1]["nominal_time"] == pytest.approx(6)
    assert body["solutions"][0]["pareto_probability"] == pytest.approx(1)
    assert body["solutions"][0]["minmax_regret"] == pytest.approx(4 / 6)
    assert body["solutions"][1]["minmax_regret"] == pytest.approx(1)
    assert body["solutions"][1]["minmax_regret_p95"] == pytest.approx(1)
    assert body["solutions"][1]["pareto_probability"] == pytest.approx(1)
    assert body["dominance"][0][1] == pytest.approx(0)
    assert body["sensitivity"] is None
    assert body["warnings"] == [
        "A distância ou o tempo recalculados de sol_near diferem dos valores mapeados."
    ]
    assert "não são reotimizadas" in body["note"]
    assert body["cloud"]["times"]

    restored = app.test_client().get("/api/v1/runs/run_robust/robustness")

    assert restored.status_code == 200
    assert restored.json == body


def test_robustness_uses_the_documented_defaults(app: Flask, monkeypatch) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session)
    monkeypatch.setattr("api.routes.robustness.load_matrices", lambda instance_id: _matrices())
    captured: dict = {}

    def fake(routes, distance, nominal_time, **kwargs):
        captured.update(kwargs)
        return analyze_robustness(
            routes,
            distance,
            nominal_time,
            scenarios=8,
            cv=0,
            rho=0,
            rho0=0,
            seed=1,
            include_sensitivity=False,
        )

    monkeypatch.setattr("api.routes.robustness.analyze_robustness", fake)

    response = app.test_client().post("/api/v1/instances/inst_robust/robustness", json={})

    assert response.status_code == 200
    assert captured["scenarios"] == 5000
    assert captured["seed"] == 42
    assert captured["cv"] == 0.2
    assert captured["rho"] == 0.3
    assert captured["rho0"] == 0.0
    assert captured["alpha"] == 0.95
    assert captured["convention"] == "mean"
    assert captured["include_sensitivity"] is True
    assert captured["time_limit"] is None


def test_robustness_requires_a_completed_mapping(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, run_status="running")

    response = app.test_client().post("/api/v1/instances/inst_robust/robustness", json={})

    assert response.status_code == 409
    assert response.json["error"]["code"] == "robustness_unavailable"
    assert app.test_client().get("/api/v1/runs/run_robust/robustness").status_code == 204


def test_robustness_reports_missing_instance_and_invalid_parameters(app: Flask) -> None:
    missing = app.test_client().post("/api/v1/instances/inst_missing/robustness", json={})
    invalid = app.test_client().post(
        "/api/v1/instances/inst_robust/robustness",
        json={"cv": -1},
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert invalid.json["error"]["code"] == "invalid_robustness"
