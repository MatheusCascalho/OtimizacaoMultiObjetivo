from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.models import Instance, Notification, Run, RunSolution


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

    payload = request.get_json(silent=True) or {}
    parameters = payload.get("parameters") or {}
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)

        existing = session.scalar(
            select(Run).where(
                Run.instance_id == instance_id,
                Run.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.parameters != parameters:
                return _error(
                    "idempotency_key_conflict",
                    "A mesma chave idempotente foi usada com parâmetros diferentes.",
                    409,
                )
            payload_response = _serialize_run(existing)
            payload_response["status_url"] = f"/api/v1/runs/{existing.run_id}"
            return jsonify(payload_response), 202

        algorithm_id = instance.configuration.get("algorithm_id") or "random-heuristic"
        now = datetime.now(UTC)
        run = Run(
            run_id=f"run_{uuid4().hex}",
            instance_id=instance_id,
            algorithm_id=algorithm_id,
            status="queued",
            parameters=parameters,
            progress={"completed": 0, "total": max(int(parameters.get("iterations", 50) or 50), 0), "percent": 0},
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        session.add(run)
        session.commit()

        response_payload = _serialize_run(run)
        try:
            celery_app = current_app.extensions["paretolab_celery_app"]
            celery_app.send_task("worker.execute_run", kwargs={"run_id": run.run_id})
        except Exception as exc:  # pragma: no cover - defensive path
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = now
            run.updated_at = now
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
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        rows = session.scalars(
            select(Run)
            .where(Run.instance_id == instance_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        payload = {"runs": [_serialize_run(row) for row in rows], "limit": limit, "offset": offset}
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
        session.commit()
        response = _serialize_run(run)
        response["status"] = "cancel_requested"
        response["status_url"] = f"/api/v1/runs/{run.run_id}"
        return jsonify(response), 202


@runs_blueprint.get("/runs/<run_id>/results")
def get_run_results(run_id: str):
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error("run_not_completed", "Os resultados só estão disponíveis após a conclusão da execução.", 409)

        rows = session.scalars(
            select(RunSolution)
            .where(RunSolution.run_id == run_id)
            .order_by(RunSolution.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        payload = {
            "run_id": run.run_id,
            "instance_id": run.instance_id,
            "status": run.status,
            "solutions": [
                {
                    "solution_id": row.solution_id,
                    "objective_values": row.objective_values,
                    "route": row.route,
                    "dominance": row.dominance,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "limit": limit,
            "offset": offset,
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
        edges = []
        for index in range(len(route) - 1):
            source = route[index]
            target = route[index + 1]
            edges.append({"source": source, "target": target})
        payload = {"solution_id": solution.solution_id, "route": route, "edges": edges}
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

