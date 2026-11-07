from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import CityLayout, Instance, InstanceFile, Run, RunSolution


DISTANCE_CSV = b"0,10,10\n10,0,10\n10,10,0\n"
TIME_CSV = b"0,1,0.1\n0.5,0,0.2\n0.1,1,0\n"


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
            "instances/time": TIME_CSV,
            "instances/distance": DISTANCE_CSV,
        }
    )
    application.config.update(TESTING=True)
    yield application
    test_engine.dispose()


def _seed(session: Session, *, status: str = "completed", with_layout: bool = True) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    session.add(
        Instance(
            instance_id="inst_emission",
            problem_type_id="tsp-time-distance",
            catalog_version="1.0.0",
            name="Emissão",
            status="ready",
            configuration={"algorithm_id": "random-heuristic"},
            node_count=3,
        )
    )
    session.add(
        Run(
            run_id="run_emission",
            instance_id="inst_emission",
            algorithm_id="random-heuristic",
            status=status,
            parameters={"iterations": 2},
            progress={"completed": 2, "total": 2, "percent": 100},
            created_at=now,
            updated_at=now,
        )
    )
    session.add_all(
        [
            InstanceFile(
                id="file_time",
                instance_id="inst_emission",
                upload_id="upl_time",
                role="time_matrix",
                object_key="instances/time",
                sha256="a" * 64,
                size_bytes=len(TIME_CSV),
                created_at=now,
            ),
            InstanceFile(
                id="file_distance",
                instance_id="inst_emission",
                upload_id="upl_distance",
                role="distance_matrix",
                object_key="instances/distance",
                sha256="b" * 64,
                size_bytes=len(DISTANCE_CSV),
                created_at=now,
            ),
        ]
    )
    session.add_all(
        [
            RunSolution(
                solution_id="sol_a",
                run_id="run_emission",
                instance_id="inst_emission",
                objective_values={"time": 1.3, "distance": 30.0},
                route=[1, 2, 3, 1],
                dominance="non_dominated",
                round_index=1,
                created_at=now,
            ),
            RunSolution(
                solution_id="sol_b",
                run_id="run_emission",
                instance_id="inst_emission",
                objective_values={"time": 1.6, "distance": 30.0},
                route=[1, 3, 2, 1],
                dominance="dominated",
                round_index=2,
                created_at=now,
            ),
        ]
    )
    if with_layout:
        session.add_all(
            [
                CityLayout(id="layout_1", instance_id="inst_emission", city_index=0, x=0, y=0),
                CityLayout(id="layout_2", instance_id="inst_emission", city_index=1, x=10, y=0),
                CityLayout(id="layout_3", instance_id="inst_emission", city_index=2, x=10, y=10),
            ]
        )
    session.commit()


def test_emissions_return_the_speed_factor_of_each_solution(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session)

    response = app.test_client().get("/api/v1/runs/run_emission/emissions")

    assert response.status_code == 200
    body = response.json
    assert body["distance_unit"] == "km"
    assert body["time_unit"] == "h"
    assert body["co2_unit"] == "kg"
    assert body["fe_base_kg_per_km"] == pytest.approx(0.3)
    by_id = {item["solution_id"]: item for item in body["solutions"]}
    assert by_id["sol_a"]["total_speed_emission_factor"] == pytest.approx(11.1 / 9.0)
    assert by_id["sol_b"]["total_speed_emission_factor"] == pytest.approx(11.55 / 9.0)
    assert by_id["sol_a"]["co2_kg"] == pytest.approx(11.1)
    assert by_id["sol_b"]["co2_kg"] == pytest.approx(11.55)
    assert "arcs" not in by_id["sol_a"]
    assert "heatmap" not in by_id["sol_a"]


def test_solution_emission_returns_the_smoothed_density(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session)

    response = app.test_client().get("/api/v1/runs/run_emission/solutions/sol_a/emission?resolution=32")

    assert response.status_code == 200
    heatmap = response.json["heatmap"]
    assert heatmap["title"] == "Densidade de CO2 (kg, suavizada)"
    assert heatmap["unit"] == "kg"
    assert heatmap["smoothing"] == "gaussian"
    assert heatmap["resolution"] == 32
    assert heatmap["row_origin"] == "ymin"
    assert len(heatmap["grid"]) == 32
    assert len(heatmap["grid"][0]) == 32
    assert max(max(row) for row in heatmap["grid"]) > 0
    assert response.json["total_speed_emission_factor"] == pytest.approx(11.1 / 9.0)
    assert response.json["heatmap_message"] is None
    assert len(response.json["arcs"]) == 3


def test_emission_requires_a_completed_run(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session, status="running")

    response = app.test_client().get("/api/v1/runs/run_emission/emissions")

    assert response.status_code == 409
    assert response.json["error"]["code"] == "run_not_completed"


def test_emission_rejects_a_non_positive_base_factor(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session)

    response = app.test_client().get("/api/v1/runs/run_emission/emissions?fe_base=0")

    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_fe_base"


def test_missing_matrices_cannot_invent_an_emission_factor(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session)
        session.execute(delete(InstanceFile))
        session.commit()

    response = app.test_client().get("/api/v1/runs/run_emission/emissions")

    assert response.status_code == 422
    assert response.json["error"]["code"] == "matrices_unavailable"


def test_heatmap_explains_a_missing_layout(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _seed(session, with_layout=False)

    response = app.test_client().get("/api/v1/runs/run_emission/solutions/sol_b/emission")

    assert response.status_code == 200
    assert response.json["heatmap"] is None
    assert response.json["heatmap_message"]
    assert response.json["total_speed_emission_factor"] == pytest.approx(11.55 / 9.0)
