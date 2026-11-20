from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import Instance, Run, RunRobustnessAnalysis


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


def _add_completed_run(app: Flask, *, with_report: bool = True, status: str = "completed") -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Instance(
                instance_id="inst_ahp",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="Instância AHP",
                status="completed",
                configuration={"algorithm_id": "random-heuristic"},
                node_count=4,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Run(
                run_id="run_ahp",
                instance_id="inst_ahp",
                algorithm_id="random-heuristic",
                status=status,
                parameters={"iterations": 5},
                progress={"completed": 5, "total": 5, "percent": 100},
                created_at=now,
                updated_at=now,
            )
        )
        if with_report:
            session.add(
                RunRobustnessAnalysis(
                    run_id="run_ahp",
                    instance_id="inst_ahp",
                    payload={
                        "solutions": [
                            {
                                "solution_id": "route-a",
                                "label": "S1",
                                "distance": 4,
                                "nominal_time": 9,
                                "co2_kg": 12,
                                "minmax_regret": 0.08,
                            },
                            {
                                "solution_id": "route-b",
                                "label": "S2",
                                "distance": 6,
                                "nominal_time": 7,
                                "co2_kg": 10,
                                "minmax_regret": 0.03,
                            },
                        ]
                    },
                )
            )
        session.commit()


def test_ahp_endpoint_returns_python_ranking_and_consistency(app: Flask) -> None:
    _add_completed_run(app)

    response = app.test_client().post(
        "/api/v1/runs/run_ahp/ahp",
        json={
            "judgments": {
                "distance:nominalTime": 3,
                "distance:co2Kg": 1 / 3,
                "distance:minmax": 5,
                "nominalTime:co2Kg": 1 / 5,
                "nominalTime:minmax": 1 / 3,
                "co2Kg:minmax": 7,
            }
        },
    )

    assert response.status_code == 200
    assert response.json["run_id"] == "run_ahp"
    assert [item["solution_id"] for item in response.json["ranking"]] == ["route-b", "route-a"]
    assert response.json["criteria_matrix"][0][1] == pytest.approx(3)
    assert response.json["consistency"]["ratio"] > 0


def test_ahp_matrix_endpoint_returns_requested_alternative_block(app: Flask) -> None:
    _add_completed_run(app)

    response = app.test_client().post(
        "/api/v1/runs/run_ahp/ahp/matrices",
        json={"criterion": "distance", "row_offset": 1, "column_offset": 0},
    )

    assert response.status_code == 200
    assert response.json["total"] == 2
    assert response.json["matrix"] == [[1 / 9, 1]]


@pytest.mark.parametrize(
    ("run_id", "body", "expected_status"),
    [
        ("run_missing", {}, 404),
        ("run_ahp", {"judgments": {"distance:nominalTime": 2.5}}, 422),
        ("run_ahp", {"unknown": True}, 422),
    ],
)
def test_ahp_endpoint_reports_missing_runs_and_invalid_input(
    app: Flask,
    run_id: str,
    body: dict,
    expected_status: int,
) -> None:
    _add_completed_run(app)

    response = app.test_client().post(f"/api/v1/runs/{run_id}/ahp", json=body)

    assert response.status_code == expected_status
    assert response.json["error"]["code"] in {"run_not_found", "invalid_ahp"}


def test_ahp_requires_completed_run_and_robustness_report(app: Flask) -> None:
    _add_completed_run(app, status="running")
    _add_completed_run_for_second_run(app)
    client = app.test_client()

    running = client.post("/api/v1/runs/run_ahp/ahp", json={})
    missing_report = client.post("/api/v1/runs/run_ahp_no_report/ahp", json={})

    assert running.status_code == 409
    assert missing_report.status_code == 409


def _add_completed_run_for_second_run(app: Flask) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    with Session(app.extensions["paretolab_database_engine"]) as session:
        session.add(
            Run(
                run_id="run_ahp_no_report",
                instance_id="inst_ahp",
                algorithm_id="random-heuristic",
                status="completed",
                parameters={},
                progress={},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
