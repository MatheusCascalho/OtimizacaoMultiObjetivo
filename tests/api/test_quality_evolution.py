from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api import create_app
from api.settings import Settings
from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import Instance, Run, RunAttemptSample, RunSolution
from multiobjective_algorithms import ObjectiveSpec, measure_run_indicators


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


def _add_instance(
    session: Session,
    instance_id: str,
    *,
    status: str = "completed",
    problem_type_id: str = "tsp-time-distance",
) -> None:
    now = datetime(2026, 11, 6, tzinfo=UTC)
    session.add(
        Instance(
            instance_id=instance_id,
            problem_type_id=problem_type_id,
            catalog_version="1.0.0",
            name="Instância evolução",
            status=status,
            configuration={"algorithm_id": "random-heuristic"},
            node_count=3,
            created_at=now,
            updated_at=now,
        )
    )


def _add_run(
    session: Session,
    *,
    instance_id: str,
    run_id: str,
    status: str,
    algorithm_id: str,
    parameters: dict,
    solutions: list[dict],
) -> None:
    now = datetime(2026, 11, 6, tzinfo=UTC)
    session.add(
        Run(
            run_id=run_id,
            instance_id=instance_id,
            algorithm_id=algorithm_id,
            status=status,
            parameters=parameters,
            progress={"completed": 1, "total": 1, "percent": 100},
            created_at=now,
            updated_at=now,
        )
    )
    for index, solution in enumerate(solutions):
        session.add(
            RunSolution(
                solution_id=f"{run_id}_sol_{index}",
                run_id=run_id,
                instance_id=instance_id,
                objective_values={
                    key: value
                    for key, value in solution.items()
                    if key not in {"dominance", "round"}
                },
                route=[1, 2, 3, 1],
                dominance=solution.get("dominance", "non_dominated"),
                round_index=solution.get("round", 1),
                created_at=now,
            )
        )


def _add_attempts(
    session: Session,
    *,
    instance_id: str,
    run_id: str,
    attempts: list[dict],
) -> None:
    for index, sample in enumerate(attempts):
        session.add(
            RunAttemptSample(
                sample_id=f"{run_id}_smp_{index}",
                run_id=run_id,
                round_index=sample["round"],
                attempt_index=sample["attempt"],
                objective_values={
                    key: value
                    for key, value in sample.items()
                    if key not in {"round", "attempt"}
                },
            )
        )


def _samples(attempts: list[dict]) -> list[dict]:
    return [
        {
            "round": sample["round"],
            "attempt": sample["attempt"],
            "time": sample["time"],
            "distance": sample["distance"],
        }
        for sample in attempts
    ]


def test_quality_evolution_averages_runs_and_leaves_an_exact_method_out(app: Flask) -> None:
    first = [
        {"time": 4.0, "distance": 0.0, "round": 1, "attempt": 1},
        {"time": 0.0, "distance": 4.0, "round": 1, "attempt": 2},
        {"time": 3.0, "distance": 1.0, "round": 2, "attempt": 1},
        {"time": 1.0, "distance": 3.0, "round": 2, "attempt": 2},
    ]
    second = [
        {"time": 2.0, "distance": 0.0, "round": 1, "attempt": 1},
        {"time": 0.0, "distance": 2.0, "round": 1, "attempt": 2},
        {"time": 2.0, "distance": 0.5, "round": 2, "attempt": 1},
        {"time": 0.5, "distance": 2.0, "round": 2, "attempt": 2},
    ]
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_evolution")
        _add_run(
            session,
            instance_id="inst_evolution",
            run_id="run_a",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 1},
            solutions=first,
        )
        _add_attempts(session, instance_id="inst_evolution", run_id="run_a", attempts=first)
        _add_run(
            session,
            instance_id="inst_evolution",
            run_id="run_b",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 2},
            solutions=second,
        )
        _add_attempts(session, instance_id="inst_evolution", run_id="run_b", attempts=second)
        _add_run(
            session,
            instance_id="inst_evolution",
            run_id="run_exact",
            status="completed",
            algorithm_id="epsilon-constraint",
            parameters={"iterations": 1},
            solutions=[{"time": 100.0, "distance": 100.0, "round": 1}],
        )
        _add_attempts(
            session,
            instance_id="inst_evolution",
            run_id="run_exact",
            attempts=[{"time": 100.0, "distance": 100.0, "round": 1, "attempt": 1}],
        )
        _add_run(
            session,
            instance_id="inst_evolution",
            run_id="run_unordered",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 10, "repetitions": 5, "seed": 3},
            solutions=[
                {"time": 9.0, "distance": 1.0, "round": 1},
                {"time": 1.0, "distance": 9.0, "round": 1},
            ],
        )
        session.commit()

    response = app.test_client().get("/api/v1/instances/inst_evolution/quality-evolution")

    assert response.status_code == 200
    body = response.json
    assert body["axis"] == "accumulated_samples"
    assert body["axis_label"] == "Amostragens acumuladas na rodada"
    assert body["space"] == "normalized_objectives"
    objectives = (
        ObjectiveSpec("time", "minimize"),
        ObjectiveSpec("distance", "minimize"),
    )
    measured_first = measure_run_indicators(_samples(first), objectives)
    measured_second = measure_run_indicators(_samples(second), objectives)
    hypervolume = body["hypervolume"]["curves"]
    spread = body["spread"]["curves"]
    assert [curve["label"] for curve in hypervolume] == [
        "RandomHeuristic · rodada 1",
        "RandomHeuristic · rodada 2",
    ]
    assert [curve["label"] for curve in spread] == [curve["label"] for curve in hypervolume]
    assert hypervolume[0]["points"][0]["accumulated_samples"] == 2
    assert hypervolume[0]["points"][0]["mean"] == pytest.approx(
        (measured_first[0].samples[0].hypervolume + measured_second[0].samples[0].hypervolume) / 2
    )
    assert hypervolume[1]["points"][0]["mean"] == pytest.approx(
        (measured_first[1].samples[0].hypervolume + measured_second[1].samples[0].hypervolume) / 2
    )
    assert spread[0]["points"][0]["mean"] == pytest.approx(
        (measured_first[0].samples[0].spread + measured_second[0].samples[0].spread) / 2
    )
    assert "epsilon-constraint" not in {curve["algorithm_id"] for curve in hypervolume}
    assert "amostragens" in body["note"]


def test_quality_evolution_does_not_invent_order_from_solution_id(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_old")
        _add_run(
            session,
            instance_id="inst_old",
            run_id="run_old",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 1},
            solutions=[
                {"time": 1.0, "distance": 4.0, "round": 1},
                {"time": 4.0, "distance": 1.0, "round": 1},
            ],
        )
        session.commit()

    response = app.test_client().get("/api/v1/instances/inst_old/quality-evolution")

    assert response.status_code == 200
    assert response.json["hypervolume"]["curves"] == []
    assert response.json["spread"]["curves"] == []
    assert "ordem das amostragens" in response.json["empty_message"]


def test_quality_evolution_overlays_one_curve_per_round(app: Flask) -> None:
    front = [
        {"time": 4.0, "distance": 0.0, "round": 1, "attempt": 1},
        {"time": 0.0, "distance": 4.0, "round": 1, "attempt": 2},
        {"time": 3.0, "distance": 1.0, "round": 2, "attempt": 1},
        {"time": 1.0, "distance": 3.0, "round": 2, "attempt": 2},
    ]
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_overlay")
        _add_run(
            session,
            instance_id="inst_overlay",
            run_id="run_random",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 1},
            solutions=front,
        )
        _add_attempts(session, instance_id="inst_overlay", run_id="run_random", attempts=front)
        _add_run(
            session,
            instance_id="inst_overlay",
            run_id="run_weighted",
            status="completed",
            algorithm_id="weighted-sum",
            parameters={"iterations": 20, "repetitions": 4, "seed": 8},
            solutions=front,
        )
        _add_attempts(session, instance_id="inst_overlay", run_id="run_weighted", attempts=front)
        session.commit()

    response = app.test_client().get("/api/v1/instances/inst_overlay/quality-evolution")

    assert response.status_code == 200
    curves = response.json["hypervolume"]["curves"]
    assert [(curve["algorithm_id"], curve["round"]) for curve in curves] == [
        ("random-heuristic", 1),
        ("random-heuristic", 2),
        ("weighted-sum", 1),
        ("weighted-sum", 2),
    ]
    assert [curve["algorithm_id"] for curve in response.json["spread"]["curves"]] == [
        curve["algorithm_id"] for curve in curves
    ]
    assert curves[2]["label"] == "weighted-sum · rodada 1"


def test_quality_evolution_splits_configurations_of_the_same_algorithm(app: Flask) -> None:
    front = [
        {"time": 4.0, "distance": 0.0, "round": 1, "attempt": 1},
        {"time": 0.0, "distance": 4.0, "round": 1, "attempt": 2},
        {"time": 1.0, "distance": 3.0, "round": 2, "attempt": 1},
        {"time": 3.0, "distance": 1.0, "round": 2, "attempt": 2},
    ]
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_config")
        _add_run(
            session,
            instance_id="inst_config",
            run_id="run_short",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 10, "repetitions": 5, "seed": 1},
            solutions=front,
        )
        _add_attempts(session, instance_id="inst_config", run_id="run_short", attempts=front)
        _add_run(
            session,
            instance_id="inst_config",
            run_id="run_long",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 2},
            solutions=front,
        )
        _add_attempts(session, instance_id="inst_config", run_id="run_long", attempts=front)
        session.commit()

    response = app.test_client().get("/api/v1/instances/inst_config/quality-evolution")

    assert response.status_code == 200
    labels = [curve["label"] for curve in response.json["hypervolume"]["curves"]]
    assert labels == [
        "RandomHeuristic · 10 amostragens · 5 rodadas · rodada 1",
        "RandomHeuristic · 10 amostragens · 5 rodadas · rodada 2",
        "RandomHeuristic · 50 amostragens · 5 rodadas · rodada 1",
        "RandomHeuristic · 50 amostragens · 5 rodadas · rodada 2",
    ]


def test_catalog_exact_algorithm_is_omitted_even_with_several_rounds(app: Flask) -> None:
    catalog = app.extensions["paretolab_catalog"]
    original = catalog.get_problem_type

    def marked(problem_type_id: str):
        problem = original(problem_type_id)
        if problem:
            for algorithm in problem.get("algorithms") or []:
                if algorithm.get("id") == "random-heuristic":
                    algorithm["exact"] = True
        return problem

    catalog.get_problem_type = marked
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_catalog_exact")
        _add_run(
            session,
            instance_id="inst_catalog_exact",
            run_id="run_catalog_exact",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5, "seed": 1},
            solutions=[
                {"time": 4.0, "distance": 0.0, "round": 1},
                {"time": 0.0, "distance": 4.0, "round": 1},
                {"time": 1.0, "distance": 3.0, "round": 2},
                {"time": 3.0, "distance": 1.0, "round": 2},
            ],
        )
        _add_attempts(
            session,
            instance_id="inst_catalog_exact",
            run_id="run_catalog_exact",
            attempts=[
                {"time": 4.0, "distance": 0.0, "round": 1, "attempt": 1},
                {"time": 0.0, "distance": 4.0, "round": 1, "attempt": 2},
                {"time": 1.0, "distance": 3.0, "round": 2, "attempt": 1},
                {"time": 3.0, "distance": 1.0, "round": 2, "attempt": 2},
            ],
        )
        session.commit()

    response = app.test_client().get("/api/v1/instances/inst_catalog_exact/quality-evolution")

    assert response.status_code == 200
    assert response.json["hypervolume"]["curves"] == []
    assert response.json["spread"]["curves"] == []


def test_quality_evolution_errors_and_empty_instances(app: Flask) -> None:
    with Session(app.extensions["paretolab_database_engine"]) as session:
        _add_instance(session, "inst_empty")
        _add_instance(session, "inst_deleting", status="deleting")
        _add_instance(session, "inst_unknown", problem_type_id="missing-type")
        _add_instance(session, "inst_invalid")
        _add_instance(session, "inst_running")
        _add_run(
            session,
            instance_id="inst_invalid",
            run_id="run_invalid",
            status="completed",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5},
            solutions=[
                {"time": 1.0, "round": 1},
                {"time": 2.0, "round": 2},
            ],
        )
        _add_attempts(
            session,
            instance_id="inst_invalid",
            run_id="run_invalid",
            attempts=[
                {"time": 1.0, "round": 1, "attempt": 1},
                {"time": 2.0, "round": 2, "attempt": 1},
            ],
        )
        _add_run(
            session,
            instance_id="inst_running",
            run_id="run_running",
            status="running",
            algorithm_id="random-heuristic",
            parameters={"iterations": 50, "repetitions": 5},
            solutions=[
                {"time": 4.0, "distance": 0.0, "round": 1},
                {"time": 0.0, "distance": 4.0, "round": 1},
                {"time": 1.0, "distance": 3.0, "round": 2},
                {"time": 3.0, "distance": 1.0, "round": 2},
            ],
        )
        session.commit()

    client = app.test_client()
    missing = client.get("/api/v1/instances/inst_missing/quality-evolution")
    deleting = client.get("/api/v1/instances/inst_deleting/quality-evolution")
    unknown = client.get("/api/v1/instances/inst_unknown/quality-evolution")
    invalid = client.get("/api/v1/instances/inst_invalid/quality-evolution")
    empty = client.get("/api/v1/instances/inst_empty/quality-evolution")
    running = client.get("/api/v1/instances/inst_running/quality-evolution")

    assert missing.status_code == 404
    assert missing.json["error"]["code"] == "instance_not_found"
    assert deleting.status_code == 409
    assert deleting.json["error"]["code"] == "instance_unavailable"
    assert unknown.status_code == 422
    assert unknown.json["error"]["code"] == "unknown_problem_type"
    assert invalid.status_code == 422
    assert invalid.json["error"]["code"] == "invalid_quality_evolution"
    assert empty.status_code == 200
    assert empty.json["hypervolume"]["curves"] == []
    assert empty.json["spread"]["curves"] == []
    assert "empty_message" not in empty.json
    assert running.status_code == 200
    assert running.json["hypervolume"]["curves"] == []
