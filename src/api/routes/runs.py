from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.pagination import get_pagination_args
from infrastructure.persistence.postgres.models import CityLayout, Instance, Notification, Run, RunSolution
from workflow_instance.domain.frontier_sampling import (
    DEFAULT_ITERATIONS,
    FRONTIER_REPETITIONS,
    total_attempts,
)


runs_blueprint = Blueprint("runs", __name__, url_prefix="/api/v1")


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


def _serialize_solution(row: RunSolution) -> dict:
    return {
        "solution_id": row.solution_id,
        "objective_values": row.objective_values,
        "route": row.route,
        "dominance": row.dominance,
        "round": row.round_index,
        "created_at": row.created_at.isoformat(),
    }


def _frontier_groups(rows: list[RunSolution]) -> list[dict]:
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        if row.dominance != "non_dominated":
            continue
        grouped.setdefault(row.round_index, []).append(_serialize_solution(row))
    return [
        {"round": round_index, "solutions": solutions}
        for round_index, solutions in sorted(grouped.items())
    ]


def _serialize_run(run: Run) -> dict:
    return {
        "run_id": run.run_id,
        "instance_id": run.instance_id,
        "algorithm_id": run.algorithm_id,
        "status": run.status,
        "progress": run.progress or {"completed": 0, "total": 0, "percent": 0},
        "parameters": run.parameters or {},
        "created_at": run.created_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "updated_at": run.updated_at.isoformat(),
        "error": run.error_message,
    }


@runs_blueprint.post("/instances/<instance_id>/runs")
def create_run(instance_id: str):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return _error("missing_idempotency_key", "O header Idempotency-Key é obrigatório.", 400)
    if len(idempotency_key) > 128:
        return _error("invalid_idempotency_key", "O header Idempotency-Key excede 128 caracteres.", 422)

    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return _error("invalid_run_payload", "O corpo da execução deve ser um objeto JSON.", 422)
    requested_parameters = payload.get("parameters", {})
    if requested_parameters is None:
        requested_parameters = {}
    if not isinstance(requested_parameters, dict):
        return _error("invalid_run_parameters", "Os parâmetros da execução devem ser um objeto.", 422)
    if set(requested_parameters) - {"iterations", "seed"}:
        return _error("invalid_run_parameters", "A execução aceita somente iterations e seed.", 422)
    iterations = requested_parameters.get("iterations", DEFAULT_ITERATIONS)
    seed = requested_parameters.get("seed")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= 100000:
        return _error("invalid_iterations", "iterations deve ser um inteiro entre 1 e 100000.", 422)
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        return _error("invalid_seed", "seed deve ser um inteiro.", 422)

    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.scalar(
            select(Instance).where(Instance.instance_id == instance_id).with_for_update()
        )
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        if instance.status == "deleting":
            return _error("instance_unavailable", "A instância está sendo excluída.", 409)

        existing = session.scalar(
            select(Run).where(
                Run.instance_id == instance_id,
                Run.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            expected_parameters = {"iterations": iterations, "repetitions": FRONTIER_REPETITIONS}
            if seed is not None:
                expected_parameters["seed"] = seed
            if any(existing.parameters.get(key) != value for key, value in expected_parameters.items()):
                return _error(
                    "idempotency_key_conflict",
                    "A mesma chave idempotente foi usada com parâmetros diferentes.",
                    409,
                )
            payload_response = _serialize_run(existing)
            payload_response["status_url"] = f"/api/v1/runs/{existing.run_id}"
            return jsonify(payload_response), 202

        active_run = session.scalar(
            select(Run.run_id).where(
                Run.instance_id == instance_id,
                Run.status.in_(["queued", "running", "cancel_requested"]),
            )
        )
        if active_run is not None:
            return _error("instance_run_active", "A instância já possui uma execução ativa.", 409)

        algorithm_id = instance.configuration.get("algorithm_id") or "random-heuristic"
        parameters = {
            "iterations": iterations,
            "repetitions": FRONTIER_REPETITIONS,
            "seed": seed if seed is not None else secrets.randbits(32),
        }
        now = datetime.now(UTC)
        run = Run(
            run_id=f"run_{uuid4().hex}",
            instance_id=instance_id,
            algorithm_id=algorithm_id,
            status="queued",
            parameters=parameters,
            progress={"completed": 0, "total": total_attempts(iterations), "percent": 0},
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(run)
        instance.status = "queued"
        instance.updated_at = now
        session.commit()

        response_payload = _serialize_run(run)
        try:
            celery_app = current_app.extensions["paretolab_celery_app"]
            celery_app.send_task("worker.execute_run", kwargs={"run_id": run.run_id})
        except Exception:  # pragma: no cover - defensive path
            current_app.logger.exception("Could not publish run %s", run.run_id)
            run.status = "failed"
            run.error_message = "Não foi possível publicar a execução no broker de tarefas."
            run.finished_at = now
            run.updated_at = now
            instance.status = "failed"
            instance.updated_at = now
            session.commit()
            payload = {
                "error": {
                    "code": "task_publish_failed",
                    "message": "Não foi possível publicar a execução no broker de tarefas.",
                    "details": [{"run_id": run.run_id}],
                }
            }
            return jsonify(payload), 503

        response_payload["status_url"] = f"/api/v1/runs/{run.run_id}"
        return jsonify(response_payload), 202


@runs_blueprint.get("/instances/<instance_id>/runs")
def list_runs(instance_id: str):
    pagination = get_pagination_args()
    if pagination is None:
        return _error("invalid_pagination", "Use limit entre 1 e 200 e offset maior ou igual a zero.", 422)
    limit, offset = pagination
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        total = session.scalar(select(func.count()).select_from(Run).where(Run.instance_id == instance_id)) or 0
        rows = session.scalars(
            select(Run)
            .where(Run.instance_id == instance_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        payload = {"runs": [_serialize_run(row) for row in rows], "limit": limit, "offset": offset, "total": total}
    return jsonify(payload), 200


@runs_blueprint.get("/runs/<run_id>")
def get_run(run_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        response = _serialize_run(run)
        response["status_url"] = f"/api/v1/runs/{run.run_id}"
        return jsonify(response), 200


@runs_blueprint.post("/runs/<run_id>/cancel")
def cancel_run(run_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status in {"completed", "cancelled", "failed"}:
            return _error(
                "run_not_cancellable",
                "A execução solicitada já se encontra em um estado terminal.",
                409,
            )
        if run.status == "cancel_requested":
            response = _serialize_run(run)
            response["status"] = "cancel_requested"
            response["status_url"] = f"/api/v1/runs/{run.run_id}"
            return jsonify(response), 202

        run.status = "cancel_requested"
        run.updated_at = datetime.now(UTC)
        instance = session.get(Instance, run.instance_id)
        if instance is not None:
            instance.status = "cancel_requested"
            instance.updated_at = run.updated_at
        session.commit()
        response = _serialize_run(run)
        response["status"] = "cancel_requested"
        response["status_url"] = f"/api/v1/runs/{run.run_id}"
        return jsonify(response), 202


@runs_blueprint.get("/runs/<run_id>/results")
def get_run_results(run_id: str):
    pagination = get_pagination_args()
    if pagination is None:
        return _error("invalid_pagination", "Use limit entre 1 e 200 e offset maior ou igual a zero.", 422)
    limit, offset = pagination
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("run_not_completed", "Os resultados só estão disponíveis após a conclusão da execução.", 409)

        total = session.scalar(select(func.count()).select_from(RunSolution).where(RunSolution.run_id == run_id)) or 0
        non_dominated = session.scalar(
            select(func.count()).select_from(RunSolution).where(
                RunSolution.run_id == run_id,
                RunSolution.dominance == "non_dominated",
            )
        ) or 0
        rows = session.scalars(
            select(RunSolution)
            .where(RunSolution.run_id == run_id)
            .order_by(RunSolution.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        frontier_rows = session.scalars(
            select(RunSolution)
            .where(
                RunSolution.run_id == run_id,
                RunSolution.dominance == "non_dominated",
            )
            .order_by(RunSolution.round_index.asc(), RunSolution.solution_id.asc())
        ).all()
        payload = {
            "run_id": run.run_id,
            "instance_id": run.instance_id,
            "status": run.status,
            "repetitions": (run.parameters or {}).get("repetitions", FRONTIER_REPETITIONS),
            "solutions": [_serialize_solution(row) for row in rows],
            "frontiers": _frontier_groups(frontier_rows),
            "limit": limit,
            "offset": offset,
            "total": total,
            "non_dominated": non_dominated,
        }
    return jsonify(payload), 200


@runs_blueprint.get("/runs/<run_id>/solutions/<solution_id>")
def get_run_solution(run_id: str, solution_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("run_not_completed", "Os resultados só estão disponíveis após a conclusão da execução.", 409)

        solution = session.get(RunSolution, solution_id)
        if solution is None or solution.run_id != run_id:
            return _error("solution_not_found", "A solução solicitada não existe para esta execução.", 404)

        payload = {
            "solution_id": solution.solution_id,
            "run_id": solution.run_id,
            "instance_id": solution.instance_id,
            "objective_values": solution.objective_values,
            "route": solution.route,
            "dominance": solution.dominance,
            "round": solution.round_index,
            "created_at": solution.created_at.isoformat(),
        }
    return jsonify(payload), 200


@runs_blueprint.get("/runs/<run_id>/solutions/<solution_id>/graph")
def get_run_solution_graph(run_id: str, solution_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("run_not_completed", "Os resultados só estão disponíveis após a conclusão da execução.", 409)
        solution = session.get(RunSolution, solution_id)
        if solution is None or solution.run_id != run_id:
            return _error("solution_not_found", "A solução solicitada não existe para esta execução.", 404)

        route = solution.route or []
        layout_rows = session.scalars(
            select(CityLayout)
            .where(CityLayout.instance_id == solution.instance_id)
            .order_by(CityLayout.city_index.asc())
        ).all()
        nodes = [
            {"id": row.city_index + 1, "label": str(row.city_index + 1), "x": row.x, "y": row.y}
            for row in layout_rows
        ]
        edges = []
        for index in range(len(route) - 1):
            source = route[index]
            target = route[index + 1]
            edges.append({"source": source, "target": target})
        payload = {"solution_id": solution.solution_id, "route": route, "nodes": nodes, "edges": edges}
    return jsonify(payload), 200


@runs_blueprint.get("/runs/<run_id>/solutions/<solution_id>/route.csv")
def get_run_solution_csv(run_id: str, solution_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("run_not_completed", "Os resultados só estão disponíveis após a conclusão da execução.", 409)
        solution = session.get(RunSolution, solution_id)
        if solution is None or solution.run_id != run_id:
            return _error("solution_not_found", "A solução solicitada não existe para esta execução.", 404)

        rows = ["sequence,city_id"]
        for sequence, city_id in enumerate(solution.route):
            rows.append(f"{sequence},{city_id}")
        if solution.route and solution.route[0] != solution.route[-1]:
            rows.append(f"{len(solution.route)},{solution.route[0]}")
    return "\n".join(rows), 200, {"Content-Type": "text/csv; charset=utf-8"}

