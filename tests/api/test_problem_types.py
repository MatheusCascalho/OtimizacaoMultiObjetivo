from flask import Flask

from api import create_app
from api.settings import Settings


def build_app() -> Flask:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:password@localhost/paretolab",
        celery_broker_url="redis://localhost:6379/0",
        s3_endpoint_url="http://localhost:9000",
        s3_bucket="paretolab-local",
        s3_access_key="local-access",
        s3_secret_key="local-secret",
    )
    app = create_app(settings)
    app.config.update(TESTING=True)
    return app


def test_list_problem_types_returns_catalog_summary() -> None:
    app = build_app()

    response = app.test_client().get("/api/v1/problem-types")

    assert response.status_code == 200
    assert response.json == {
        "problem_types": [
            {
                "id": "tsp-time-distance",
                "name": "TSP biobjetivo: tempo e distância",
                "version": "1.0.0",
            }
        ]
    }
    app.extensions["paretolab_database_engine"].dispose()


def test_get_problem_type_includes_objectives_and_supported_algorithm() -> None:
    app = build_app()

    response = app.test_client().get("/api/v1/problem-types/tsp-time-distance")

    assert response.status_code == 200
    assert response.json["objectives"] == [
        {"id": "time", "name": "Tempo", "unit": "h", "direction": "minimize"},
        {"id": "distance", "name": "Distância", "unit": "km", "direction": "minimize"},
    ]
    algorithms = response.json["algorithms"]
    assert [algorithm["id"] for algorithm in algorithms] == [
        "random-heuristic",
        "neuro-lkh",
    ]
    assert algorithms[0]["name"] == "RandomHeuristic"
    assert algorithms[0]["method"] == "heuristic"
    assert [parameter["id"] for parameter in algorithms[0]["parameters"]] == [
        "iterations",
        "seed",
    ]
    assert algorithms[0]["parameters"][0] == {
        "id": "iterations",
        "type": "integer",
        "default": 50,
        "minimum": 1,
        "maximum": 100000,
    }
    assert algorithms[1]["name"] == "NeuroLKH"
    assert algorithms[1]["method"] == "heuristic"
    assert [parameter["id"] for parameter in algorithms[1]["parameters"]] == [
        "iterations",
        "seed",
        "lkh_trials",
    ]
    assert "weight" not in {parameter["id"] for parameter in algorithms[0]["parameters"]}
    app.extensions["paretolab_database_engine"].dispose()


def test_get_unknown_problem_type_returns_standardized_not_found() -> None:
    app = build_app()

    response = app.test_client().get("/api/v1/problem-types/unknown")

    assert response.status_code == 404
    assert response.json == {
        "error": {
            "code": "problem_type_not_found",
            "message": "O tipo de problema solicitado não existe.",
            "details": [],
        }
    }
    app.extensions["paretolab_database_engine"].dispose()