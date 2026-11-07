"""Robustness of the mapped approximate Pareto front."""

from __future__ import annotations

from numbers import Integral, Real

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import CityLayout, Instance, Run, RunSolution
from multiobjective_algorithms import analyze_robustness, non_dominated_mask
from multiobjective_algorithms.robustness import (
    RobustnessReport,
    SensitivityPoint,
    SolutionRobustness,
    parameters_as_mapping,
)


robustness_blueprint = Blueprint("robustness", __name__, url_prefix="/api/v1")

_ANALYSIS_NOTE = (
    "As rotas da fronteira aproximada permanecem fixas. "
    "Cada cenário perturba somente os tempos dos arcos usados, "
    "e todas as soluções são avaliadas nos mesmos cenários. "
    "A distância não é perturbada e as rotas não são reotimizadas."
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


def load_matrices(instance_id: str):
    from api.routes.instances import _get_instance_matrix

    return (
        _get_instance_matrix(instance_id, "time_matrix"),
        _get_instance_matrix(instance_id, "distance_matrix"),
    )


@robustness_blueprint.post("/instances/<instance_id>/robustness")
def analyze_instance_robustness(instance_id: str):
    parameters, error = _request_parameters()
    if error is not None:
        return error

    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        if instance.status == "deleting":
            return _error("instance_unavailable", "A instância está sendo excluída.", 409)
        run = session.scalar(
            select(Run).where(Run.instance_id == instance_id).order_by(Run.created_at.desc())
        )
        if run is None or run.status != "completed":
            return _error(
                "robustness_unavailable",
                "A análise de robustez exige uma execução concluída com soluções mapeadas.",
                409,
            )
        rows = session.scalars(select(RunSolution).where(RunSolution.run_id == run.run_id)).all()
        if not rows:
            return _error(
                "robustness_unavailable",
                "A execução concluída não tem soluções mapeadas.",
                409,
            )
        try:
            front = _approximate_front(rows)
        except ValueError as error:
            return _error("invalid_solutions", str(error), 422)
        layout = session.scalars(
            select(CityLayout)
            .where(CityLayout.instance_id == instance_id)
            .order_by(CityLayout.city_index.asc())
        ).all()
        coordinates = (
            [(row.x, row.y) for row in layout]
            if [row.city_index for row in layout] == list(range(instance.node_count))
            else None
        )
        run_id = run.run_id

    try:
        time_matrix, distance_matrix = load_matrices(instance_id)
    except (KeyError, OSError, ValueError):
        return _error(
            "matrices_unavailable",
            "Não foi possível ler as matrizes de tempo e distância desta instância.",
            409,
        )
    if coordinates is not None and len(coordinates) != len(time_matrix):
        coordinates = None

    try:
        report = analyze_robustness(
            [row.route for row in front],
            distance_matrix,
            time_matrix,
            coordinates=coordinates,
            **parameters,
        )
    except ValueError as error:
        return _error("invalid_robustness", str(error), 422)

    warnings = _objective_warnings(front, report)
    return jsonify(_payload(instance_id, run_id, front, report, warnings)), 200


def _request_parameters() -> tuple[dict | None, tuple | None]:
    if request.data and request.get_json(silent=True) is None:
        return None, _error("invalid_robustness", "O corpo da análise deve ser um objeto JSON.", 422)
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return None, _error("invalid_robustness", "O corpo da análise deve ser um objeto JSON.", 422)
    unknown = set(payload) - {
        "scenarios",
        "seed",
        "cv",
        "rho",
        "rho0",
        "alpha",
        "time_limit",
        "convention",
        "include_sensitivity",
    }
    if unknown:
        return None, _error(
            "invalid_robustness",
            "A análise aceita scenarios, seed, cv, rho, rho0, alpha, time_limit, convention e include_sensitivity.",
            422,
        )
    parameters = {
        "scenarios": payload.get("scenarios", 5000),
        "seed": payload.get("seed", 42),
        "cv": payload.get("cv", 0.2),
        "rho": payload.get("rho", 0.3),
        "rho0": payload.get("rho0", 0.0),
        "alpha": payload.get("alpha", 0.95),
        "time_limit": payload.get("time_limit"),
        "convention": payload.get("convention", "mean"),
        "include_sensitivity": payload.get("include_sensitivity", True),
    }
    if not isinstance(parameters["include_sensitivity"], bool):
        return None, _error("invalid_robustness", "include_sensitivity deve ser verdadeiro ou falso.", 422)
    if parameters["convention"] not in {"mean", "median"}:
        return None, _error("invalid_robustness", "convention deve ser mean ou median.", 422)
    if not _is_number(parameters["scenarios"], integral=True) or not 1 <= int(parameters["scenarios"]) <= 20_000:
        return None, _error("invalid_robustness", "scenarios deve ser um inteiro entre 1 e 20000.", 422)
    if not _is_number(parameters["seed"], integral=True):
        return None, _error("invalid_robustness", "seed deve ser um inteiro.", 422)
    for name in ("cv", "rho", "rho0", "alpha"):
        if not _is_number(parameters[name]):
            return None, _error("invalid_robustness", f"{name} deve ser um número finito.", 422)
    if float(parameters["cv"]) < 0 or float(parameters["rho"]) < 0 or float(parameters["rho0"]) < 0:
        return None, _error("invalid_robustness", "cv, rho e rho0 devem ser maiores ou iguais a zero.", 422)
    if float(parameters["rho"]) + float(parameters["rho0"]) >= 1:
        return None, _error("invalid_robustness", "rho e rho0 devem somar menos de 1.", 422)
    if not 0 < float(parameters["alpha"]) < 1:
        return None, _error("invalid_robustness", "alpha deve estar estritamente entre 0 e 1.", 422)
    if parameters["time_limit"] is not None and not _is_number(parameters["time_limit"]):
        return None, _error("invalid_robustness", "time_limit deve ser um número finito.", 422)
    parameters["scenarios"] = int(parameters["scenarios"])
    parameters["seed"] = int(parameters["seed"])
    return parameters, None


def _approximate_front(rows: list[RunSolution]) -> list[RunSolution]:
    objectives = [(_objective(row, "time"), _objective(row, "distance")) for row in rows]
    mask = non_dominated_mask(objectives, ("minimize", "minimize"))
    front = [row for row, keep in zip(rows, mask) if keep]
    front.sort(key=lambda row: (_objective(row, "distance"), _objective(row, "time"), row.solution_id))
    unique: list[RunSolution] = []
    seen: set[tuple] = set()
    for row in front:
        if not isinstance(row.route, list) or not row.route:
            raise ValueError("cada solução mapeada precisa ter uma rota")
        key = tuple(row.route)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    if not unique:
        raise ValueError("a fronteira aproximada não tem rotas para avaliar")
    return unique


def _objective(row: RunSolution, key: str) -> float:
    values = row.objective_values if isinstance(row.objective_values, dict) else None
    value = None if values is None else values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("as soluções mapeadas precisam informar tempo e distância finitos")
    return float(value)


def _objective_warnings(rows: list[RunSolution], report: RobustnessReport) -> list[str]:
    warnings: list[str] = []
    if report.deterministic_zero_arcs:
        warnings.append(_zero_arc_warning(report.deterministic_zero_arcs))
    for row, solution in zip(rows, report.solutions):
        stored_time = _objective(row, "time")
        stored_distance = _objective(row, "distance")
        if _differs(stored_time, solution.nominal_time) or _differs(stored_distance, solution.distance):
            warnings.append(
                f"A distância ou o tempo recalculados de {row.solution_id} diferem dos valores mapeados."
            )
    return warnings


def _zero_arc_warning(count: int) -> str:
    if count == 1:
        return "1 arco usado tem tempo nominal zero e permanece igual a zero em todos os cenários."
    formatted = f"{count:,}".replace(",", ".")
    return (
        f"{formatted} arcos usados têm tempo nominal zero e permanecem iguais a zero em todos os cenários."
    )


def _differs(stored: float, recalculated: float) -> bool:
    return abs(stored - recalculated) > max(1e-6, 1e-4 * abs(stored))


def _payload(
    instance_id: str,
    run_id: str,
    rows: list[RunSolution],
    report: RobustnessReport,
    warnings: list[str],
) -> dict:
    solutions = [
        _solution_payload(row.solution_id, index + 1, solution)
        for index, (row, solution) in enumerate(zip(rows, report.solutions))
    ]
    sensitivity = None
    if report.parameters.sensitivity_scenarios is not None:
        sensitivity = {
            "by_cv": [_sensitivity_payload(point) for point in report.sensitivity_by_cv],
            "by_rho": [_sensitivity_payload(point) for point in report.sensitivity_by_rho],
            "ranking_inversion_cv": report.ranking_inversion_cv,
            "frontier_loss_cv": report.frontier_loss_cv,
        }
    return {
        "instance_id": instance_id,
        "run_id": run_id,
        "solution_count": len(solutions),
        "parameters": dict(parameters_as_mapping(report.parameters)),
        "warnings": warnings,
        "note": _ANALYSIS_NOTE,
        "hypervolume": {
            "reference": {
                "distance": report.reference_distance,
                "time": report.reference_time,
            },
            "mean": report.mean_hypervolume,
            "stdev": report.stdev_hypervolume,
        },
        "solutions": solutions,
        "dominance": [list(row) for row in report.dominance],
        "cloud": {"times": [list(row) for row in report.cloud_times]},
        "sensitivity": sensitivity,
    }


def _solution_payload(solution_id: str, label_index: int, solution: SolutionRobustness) -> dict:
    return {
        "solution_id": solution_id,
        "label": f"S{label_index}",
        "distance": solution.distance,
        "nominal_time": solution.nominal_time,
        "mean": solution.mean,
        "stdev": solution.stdev,
        "coefficient_of_variation": solution.coefficient_of_variation,
        "p50": solution.p50,
        "p90": solution.p90,
        "p95": solution.p95,
        "p99": solution.p99,
        "worst": solution.worst,
        "var": solution.var,
        "cvar": solution.cvar,
        "violation_probability": solution.violation_probability,
        "p95_degradation": solution.p95_degradation,
        "mean_ci_low": solution.mean_ci_low,
        "mean_ci_high": solution.mean_ci_high,
        "win_frequency": solution.win_frequency,
        "pareto_probability": solution.pareto_probability,
        "regret_mean": solution.regret_mean,
        "regret_p95": solution.regret_p95,
        "regret_max": solution.regret_max,
        "distance_regret": solution.distance_regret,
        "hypervolume_contribution": solution.hypervolume_contribution,
        "minmax_regret": solution.minmax_regret,
        "minmax_regret_p95": solution.minmax_regret_p95,
        "rank_frequencies": list(solution.rank_frequencies),
        "boxplot": {
            "min": solution.box_min,
            "q1": solution.box_q1,
            "median": solution.p50,
            "q3": solution.box_q3,
            "max": solution.box_max,
            "nominal": solution.nominal_time,
        },
        "critical_arcs": [
            {
                "source": arc.source,
                "target": arc.target,
                "nominal_time": arc.nominal_time,
                "variance_share": arc.variance_share,
                "correlation": arc.correlation,
            }
            for arc in solution.critical_arcs
        ],
    }


def _sensitivity_payload(point: SensitivityPoint) -> dict:
    return {
        "cv": point.cv,
        "rho": point.rho,
        "mean": list(point.mean),
        "p95": list(point.p95),
        "cvar": list(point.cvar),
        "pareto_probability": list(point.pareto_probability),
        "win_frequency": list(point.win_frequency),
    }


def _is_number(value: object, *, integral: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    if integral:
        return isinstance(value, Integral)
    return isinstance(value, Real)
