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
            name="Instância referência",
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


def test_reference_points_use_lexicographic_selection_on_the_mapped_front(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(
            session,
            run_id="run_reference",
            status="completed",
            solutions=[
                {"time": 4.0, "distance": 0.0, "dominance": "non_dominated"},
                {"time": 0.0, "distance": 4.0, "dominance": "non_dominated"},
                {"time": 0.0, "distance": 9.0, "dominance": "dominated"},
                {"time": 2.0, "distance": 2.0, "dominance": "non_dominated", "round": 2},
            ],
        )

    response = app.test_client().get("/api/v1/runs/run_reference/reference-points")

    assert response.status_code == 200
    body = response.json
    assert body["run_id"] == "run_reference"
    assert body["method"] == "approximate_front"
    assert body["antiutopian_kind"] == "nadir"
    assert body["utopian"]["label"] == "Solução utópica"
    assert body["antiutopian"]["label"] == "Solução antiutópica"
    assert body["utopian"]["objective_values"] == {"time": 0.0, "distance": 0.0}
    assert body["antiutopian"]["objective_values"] == {"time": 4.0, "distance": 4.0}
    assert body["distance"] == {
        "metric": "euclidean",
        "label": "Distância euclidiana normalizada",
        "space": "normalized_objectives",
        "note": "Cada objetivo vai de 0 no utópico a 1 no nadir.",
    }
    assert [item["id"] for item in body["objectives"]] == ["time", "distance"]
    assert body["objectives"][1]["unit"] == "km"
    assert body["warnings"] == []
    assert "nadir" in body["note"]


def test_non_conflicting_front_returns_a_warning(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(
            session,
            run_id="run_flat",
            status="completed",
            solutions=[{"time": 1.5, "distance": 2.5, "dominance": "non_dominated"}],
        )

    response = app.test_client().get("/api/v1/runs/run_flat/reference-points")

    assert response.status_code == 200
    assert response.json["utopian"]["objective_values"] == response.json["antiutopian"]["objective_values"]
    assert response.json["warnings"][0]["code"] == "non_conflicting_objectives"


def test_reference_points_require_a_completed_run_with_solutions(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_run(session, run_id="run_pending", status="running", solutions=[])
        _add_run(session, run_id="run_empty", status="completed", solutions=[])

    missing = app.test_client().get("/api/v1/runs/run_missing/reference-points")
    pending = app.test_client().get("/api/v1/runs/run_pending/reference-points")
    empty = app.test_client().get("/api/v1/runs/run_empty/reference-points")

    assert missing.status_code == 404
    assert missing.json["error"]["code"] == "run_not_found"
    assert pending.status_code == 409
    assert pending.json["error"]["code"] == "run_not_completed"
    assert empty.status_code == 409
    assert empty.json["error"]["code"] == "reference_points_unavailable"
