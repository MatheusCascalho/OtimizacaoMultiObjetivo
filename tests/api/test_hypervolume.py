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


def _add_run(session: Session, *, run_id: str, status: str, solutions: list[dict]) -> None:
    now = datetime(2026, 11, 6, tzinfo=UTC)
    session.add(
        Instance(
            instance_id=f"inst_{run_id}",
            problem_type_id="tsp-time-distance",
            catalog_version="1.0.0",
            name="Instância hipervolume",
            status="completed",
            configuration={"algorithm_id": "random-heuristic"},
            node_count=3,
        )
    )
    session.add(
        Run(
            run_id=run_id,
            instance_id=f"inst_{run_id}",
            algorithm_id="random-heuristic",
            status=status,
            parameters={"iterations": 5},
            progress={"completed": 5, "total": 5, "percent": 100},
            created_at=now,
            updated_at=now,
        )
    )
    for index, solution in enumerate(solutions):
        session.add(
            RunSolution(
                solution_id=f"{run_id}_sol_{index}",
                run_id=run_id,
                instance_id=f"inst_{run_id}",
                objective_values={"time": solution["time"], "distance": solution["distance"]},
                route=[1, 2, 3, 1],
                dominance=solution["dominance"],
                round_index=solution.get("round", 1),
                created_at=now,
            )
        )
    session.commit()


def test_hypervolume_reports_each_round_and_the_sample_aggregates(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(
            session,
            run_id="run_hv",
            status="completed",
            solutions=[
                {"time": 4.0, "distance": 0.0, "dominance": "non_dominated", "round": 1},
                {"time": 0.0, "distance": 4.0, "dominance": "non_dominated", "round": 1},
                {"time": 5.0, "distance": 5.0, "dominance": "dominated", "round": 1},
                {"time": 3.0, "distance": 1.0, "dominance": "non_dominated", "round": 2},
                {"time": 1.0, "distance": 3.0, "dominance": "non_dominated", "round": 2},
            ],
        )

    response = app.test_client().get("/api/v1/runs/run_hv/hypervolume")

    assert response.status_code == 200
    body = response.json
    assert body["run_id"] == "run_hv"
    assert body["space"] == "normalized_objectives"
    assert body["unit"] is None
    assert body["standard_deviation"] == "sample"
    assert body["reference_shift"] == 0.05
    assert body["nadir"] == {"time": 4.0, "distance": 4.0}
    assert body["reference_point"] == pytest.approx({"time": 1.05, "distance": 1.05})
    assert body["rounds"][0]["round"] == 1
    assert body["rounds"][0]["candidate_count"] == 2
    assert body["rounds"][0]["hypervolume"] == pytest.approx(0.1025)
    assert body["rounds"][1]["candidate_count"] == 2
    assert body["rounds"][1]["hypervolume"] == pytest.approx(0.39)
    assert body["mean_hypervolume"] == pytest.approx(0.24625)
    assert body["coefficient_of_variation"] == pytest.approx(
        body["sample_stdev_hypervolume"] / body["mean_hypervolume"]
    )
    assert body["mean_candidate_count"] == pytest.approx(2)
    assert body["rounds"][0]["distance_to_mean"] == pytest.approx(body["rounds"][0]["hypervolume"] - body["mean_hypervolume"])
    assert "1,05" in body["note"]
    assert "utópico" in body["note"]


def test_hypervolume_coefficient_is_zero_for_a_single_round(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(
            session,
            run_id="run_hv_one",
            status="completed",
            solutions=[
                {"time": 4.0, "distance": 0.0, "dominance": "non_dominated", "round": 1},
                {"time": 0.0, "distance": 4.0, "dominance": "non_dominated", "round": 1},
            ],
        )

    response = app.test_client().get("/api/v1/runs/run_hv_one/hypervolume")

    assert response.status_code == 200
    body = response.json
    assert body["sample_stdev_hypervolume"] == 0.0
    assert body["mean_hypervolume"] == pytest.approx(0.1025)
    assert body["coefficient_of_variation"] == 0.0


def test_hypervolume_coefficient_is_null_when_the_mean_is_zero(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(
            session,
            run_id="run_hv_zero",
            status="completed",
            solutions=[
                {"time": 0.0, "distance": 0.0, "dominance": "non_dominated", "round": 1},
                {"time": 0.0, "distance": 0.0, "dominance": "non_dominated", "round": 2},
            ],
        )

    response = app.test_client().get("/api/v1/runs/run_hv_zero/hypervolume")

    assert response.status_code == 200
    body = response.json
    assert body["mean_hypervolume"] == 0.0
    assert body["coefficient_of_variation"] is None


def test_hypervolume_requires_a_completed_run(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(session, run_id="run_pending", status="running", solutions=[])

    missing = app.test_client().get("/api/v1/runs/run_missing/hypervolume")
    pending = app.test_client().get("/api/v1/runs/run_pending/hypervolume")

    assert missing.status_code == 404
    assert missing.json["error"]["code"] == "run_not_found"
    assert pending.status_code == 409
    assert pending.json["error"]["code"] == "run_not_completed"
