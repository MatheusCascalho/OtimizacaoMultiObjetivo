"""AHP decision support for completed TSP runs."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import Run, RunRobustnessAnalysis
from multiobjective_algorithms import calculate_ahp, calculate_alternative_matrix


ahp_blueprint = Blueprint("ahp", __name__, url_prefix="/api/v1")


def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message, "details": []}}), status


@ahp_blueprint.post("/runs/<run_id>/ahp")
def rank_run_solutions(run_id: str):
    if request.data and request.get_json(silent=True) is None:
        return _error("invalid_ahp", "O corpo da decisão deve ser um objeto JSON.", 422)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) - {"judgments"}:
        return _error("invalid_ahp", "Informe apenas o objeto judgments com as comparações dos critérios.", 422)
    judgments = payload.get("judgments", {})
    if not isinstance(judgments, dict):
        return _error("invalid_ahp", "As comparações devem ser informadas como um objeto.", 422)

    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("ahp_unavailable", "A decisão AHP exige uma execução concluída.", 409)
        analysis = session.get(RunRobustnessAnalysis, run_id)
        if analysis is None:
            return _error(
                "ahp_unavailable",
                "Execute a análise de robustez para calcular Min-Max Regret e emissão de CO2 antes do ranking.",
                409,
            )
        if analysis.instance_id != run.instance_id:
            return _error("invalid_robustness_report", "O relatório de robustez não corresponde à instância da execução.", 409)
        solutions = analysis.payload.get("solutions") if isinstance(analysis.payload, dict) else None
        try:
            result = calculate_ahp(solutions, judgments)
        except ValueError as error:
            return _error("invalid_ahp", str(error), 422)

    return jsonify({"run_id": run_id, **result}), 200


@ahp_blueprint.post("/runs/<run_id>/ahp/matrices")
def get_run_ahp_matrix(run_id: str):
    if request.data and request.get_json(silent=True) is None:
        return _error("invalid_ahp", "O corpo da matriz deve ser um objeto JSON.", 422)
    payload = request.get_json(silent=True)
    allowed = {"criterion", "row_offset", "column_offset"}
    if not isinstance(payload, dict) or set(payload) - allowed or "criterion" not in payload:
        return _error(
            "invalid_ahp",
            "Informe criterion e, opcionalmente, row_offset e column_offset.",
            422,
        )
    if any(
        isinstance(payload.get(key, 0), bool) or not isinstance(payload.get(key, 0), int)
        for key in ("row_offset", "column_offset")
    ):
        return _error("invalid_ahp", "Os deslocamentos da matriz devem ser inteiros.", 422)

    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("ahp_unavailable", "A decisão AHP exige uma execução concluída.", 409)
        analysis = session.get(RunRobustnessAnalysis, run_id)
        if analysis is None or analysis.instance_id != run.instance_id:
            return _error("ahp_unavailable", "Execute uma análise de robustez válida antes de visualizar as matrizes.", 409)
        solutions = analysis.payload.get("solutions") if isinstance(analysis.payload, dict) else None
        try:
            result = calculate_alternative_matrix(
                solutions,
                payload["criterion"],
                payload.get("row_offset", 0),
                payload.get("column_offset", 0),
            )
        except ValueError as error:
            return _error("invalid_ahp", str(error), 422)

    return jsonify({"run_id": run_id, **result}), 200
