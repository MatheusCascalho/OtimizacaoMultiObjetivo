"""CO2 emission factor of each mapped TSP solution."""

from __future__ import annotations

from numbers import Integral, Real

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import CityLayout, Run, RunSolution
from optimization_problems.tsp.emission import (
    DEFAULT_FE_BASE_KG_PER_KM,
    DEFAULT_HEATMAP_RESOLUTION,
    EmissionError,
    evaluate_route_emission,
    speed_bands_payload,
)


emission_blueprint = Blueprint("emission", __name__, url_prefix="/api/v1")

_SUMMARY_FIELDS = (
    "arc_count",
    "unknown_speed_arcs",
    "distance_km",
    "base_co2_kg",
    "co2_kg",
    "excess_co2_kg",
    "total_speed_emission_factor",
)


def _error(code: str, message: str, status: int, details: list[dict] | None = None):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or [],
                }
            }
        ),
        status,
    )


def _load_matrices(instance_id: str):
    from api.routes.instances import _get_instance_matrix

    return (
        _get_instance_matrix(instance_id, "time_matrix"),
        _get_instance_matrix(instance_id, "distance_matrix"),
    )


def _fe_base():
    raw = request.args.get("fe_base")
    if raw is None or raw == "":
        return DEFAULT_FE_BASE_KG_PER_KM, None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = None
    if value is None or value != value or value in (float("inf"), float("-inf")) or value <= 0:
        return None, _error(
            "invalid_fe_base",
            "O fator base de emissão deve ser um número positivo, em kg/km.",
            422,
        )
    return value, None


def _resolution():
    raw = request.args.get("resolution")
    if raw is None or raw == "":
        return DEFAULT_HEATMAP_RESOLUTION, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = None
    if isinstance(raw, bool) or value is None or not 32 <= value <= 240:
        return None, _error(
            "invalid_resolution",
            "A resolução do heatmap deve ser um inteiro entre 32 e 240.",
            422,
        )
    return value, None


def _json_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    return float(f"{float(value):.6f}")


def _summary(identity: dict[str, object], emission: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "solution_id": identity["solution_id"],
        "round": identity["round"],
        "dominance": identity["dominance"],
    }
    for field in _SUMMARY_FIELDS:
        value = emission[field]
        payload[field] = value if isinstance(value, Integral) and not isinstance(value, bool) else _json_number(value)
    return payload


def _completed_run(session: Session, run_id: str):
    run = session.get(Run, run_id)
    if run is None:
        return None, _error("run_not_found", "A execução solicitada não existe.", 404)
    if run.status != "completed":
        return None, _error(
            "run_not_completed",
            "A emissão só está disponível após a conclusão da execução.",
            409,
        )
    return run, None


def _matrices_or_error(instance_id: str):
    try:
        time_matrix, distance_matrix = _load_matrices(instance_id)
    except KeyError:
        return None, _error(
            "matrices_unavailable",
            "A instância não tem as matrizes de tempo e distância necessárias para a emissão.",
            422,
        )
    except Exception:
        current_app.logger.exception("Falha ao ler matrizes para emissão de CO2.")
        return None, _error(
            "matrices_unavailable",
            "Não foi possível ler as matrizes de tempo e distância.",
            422,
        )
    return (time_matrix, distance_matrix), None


def _layout(session: Session, instance_id: str) -> dict[int, tuple[float, float]]:
    rows = session.scalars(
        select(CityLayout)
        .where(CityLayout.instance_id == instance_id)
        .order_by(CityLayout.city_index.asc())
    ).all()
    return {row.city_index + 1: (row.x, row.y) for row in rows}


def _context(fe_base: float) -> dict[str, object]:
    return {
        "fe_base_kg_per_km": _json_number(fe_base),
        "distance_unit": "km",
        "time_unit": "h",
        "co2_unit": "kg",
        "bands": speed_bands_payload(),
    }


@emission_blueprint.get("/runs/<run_id>/emissions")
def list_solution_emissions(run_id: str):
    fe_base, error = _fe_base()
    if error is not None:
        return error
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run, error = _completed_run(session, run_id)
        if error is not None:
            return error
        rows = session.scalars(
            select(RunSolution)
            .where(RunSolution.run_id == run_id)
            .order_by(RunSolution.solution_id.asc())
        ).all()
        instance_id = run.instance_id
        identities = [
            {
                "solution_id": row.solution_id,
                "round": row.round_index,
                "dominance": row.dominance,
                "route": list(row.route or []),
            }
            for row in rows
        ]
    matrices, error = _matrices_or_error(instance_id)
    if error is not None:
        return error
    time_matrix, distance_matrix = matrices
    solutions = []
    for identity in identities:
        try:
            emission = evaluate_route_emission(
                identity["route"],
                distance_matrix,
                time_matrix,
                fe_base_kg_per_km=fe_base,
                close_cycle=True,
            )
        except EmissionError as error:
            return _error("invalid_route", str(error), 422)
        solutions.append(_summary(identity, emission))
    payload = {
        "run_id": run_id,
        "instance_id": instance_id,
        **_context(fe_base),
        "solutions": solutions,
    }
    return jsonify(payload), 200


@emission_blueprint.get("/runs/<run_id>/solutions/<solution_id>/emission")
def get_solution_emission(run_id: str, solution_id: str):
    fe_base, error = _fe_base()
    if error is not None:
        return error
    resolution, error = _resolution()
    if error is not None:
        return error
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run, error = _completed_run(session, run_id)
        if error is not None:
            return error
        solution = session.get(RunSolution, solution_id)
        if solution is None or solution.run_id != run_id:
            return _error("solution_not_found", "A solução solicitada não existe para esta execução.", 404)
        nodes = _layout(session, solution.instance_id)
        instance_id = solution.instance_id
        identity = {
            "solution_id": solution.solution_id,
            "round": solution.round_index,
            "dominance": solution.dominance,
            "route": list(solution.route or []),
        }
    matrices, error = _matrices_or_error(instance_id)
    if error is not None:
        return error
    time_matrix, distance_matrix = matrices
    try:
        emission = evaluate_route_emission(
            identity["route"],
            distance_matrix,
            time_matrix,
            nodes=nodes,
            fe_base_kg_per_km=fe_base,
            close_cycle=True,
            include_arcs=True,
            include_heatmap=True,
            resolution=resolution,
        )
    except EmissionError as error:
        return _error("invalid_route", str(error), 422)
    payload = {
        "run_id": run_id,
        "instance_id": instance_id,
        **_context(fe_base),
        **_summary(identity, emission),
        "arcs": [
            {
                **arc,
                "distance_km": _json_number(arc["distance_km"]),
                "time_h": _json_number(arc["time_h"]),
                "speed_kmh": _json_number(arc["speed_kmh"]),
                "speed_factor": _json_number(arc["speed_factor"]),
                "co2_kg": _json_number(arc["co2_kg"]),
            }
            for arc in emission["arcs"]
        ],
        "heatmap": emission["heatmap"],
        "heatmap_message": emission["heatmap_message"],
    }
    return jsonify(payload), 200
