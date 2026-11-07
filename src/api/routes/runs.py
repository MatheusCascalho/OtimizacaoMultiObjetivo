from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.pagination import get_pagination_args
from infrastructure.persistence.postgres.models import (
    CityLayout,
    Instance,
    Notification,
    Run,
    RunAttemptSample,
    RunSolution,
)
from multiobjective_algorithms import (
    ObjectiveSpec,
    ReferencePointError,
    aggregate_quality_evolution,
    configuration_key,
    estimate_reference_points,
    is_exact_execution,
    measure_run_indicators,
    summarize_run_hypervolume,
    summarize_run_spread,
)
from multiobjective_algorithms.quality_evolution import (
    ACCUMULATED_SAMPLES_AXIS,
    MeanCurve,
    RunIndicatorTrack,
    stable_number,
)
from workflow_instance.domain.frontier_sampling import (
    DEFAULT_ITERATIONS,
    FRONTIER_REPETITIONS,
    total_attempts,
)
from workflow_instance.domain.solution_timing import solution_timing_kpis


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
            "solution_timing": solution_timing_kpis(run.solution_timings),
            "limit": limit,
            "offset": offset,
            "total": total,
            "non_dominated": non_dominated,
        }
    return jsonify(payload), 200


@runs_blueprint.get("/runs/<run_id>/reference-points")
def get_run_reference_points(run_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error(
                "run_not_completed",
                "Os pontos de referência só estão disponíveis após a conclusão da execução.",
                409,
            )
        instance = session.get(Instance, run.instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância da execução não existe.", 404)
        problem_type = current_app.extensions["paretolab_catalog"].get_problem_type(instance.problem_type_id)
        if problem_type is None:
            return _error(
                "unknown_problem_type",
                "O tipo de problema da instância não está no catálogo.",
                422,
            )
        rows = session.scalars(select(RunSolution).where(RunSolution.run_id == run_id)).all()
        try:
            objectives = _reference_objectives(problem_type, rows)
            result = estimate_reference_points(
                [row.objective_values for row in rows],
                objectives,
            )
        except ReferencePointError as error:
            details = [{"stage": error.stage}] if error.stage else []
            return _error("reference_points_unavailable", str(error), 409, details)
        except ValueError as error:
            return _error("invalid_reference_points", str(error), 422)
        payload = _reference_points_payload(run.run_id, problem_type, result)
    return jsonify(payload), 200


def _reference_objectives(
    problem_type: dict,
    rows: list[RunSolution] | list[RunAttemptSample],
) -> tuple[ObjectiveSpec, ...]:
    catalog = problem_type.get("objectives") or []
    catalog_ids = [item["id"] for item in catalog]
    if len(catalog_ids) != 2 or len(set(catalog_ids)) != 2:
        raise ValueError(
            "O cálculo da solução utópica e da solução antiutópica exige exatamente 2 objetivos."
        )
    if not rows:
        raise ReferencePointError("Não há soluções mapeadas para estimar os pontos de referência.")
    sample_ids = {key for row in rows for key in (row.objective_values or {})}
    if sample_ids != set(catalog_ids):
        raise ValueError("Os objetivos da execução não coincidem com o catálogo do problema.")
    specs: list[ObjectiveSpec] = []
    for item in catalog:
        direction = item.get("direction")
        if direction not in {"minimize", "maximize"}:
            raise ValueError("A direção do objetivo no catálogo é inválida.")
        specs.append(ObjectiveSpec(item["id"], direction))
    return tuple(specs)


def _reference_points_payload(run_id: str, problem_type: dict, result) -> dict:
    catalog = {item["id"]: item for item in problem_type.get("objectives", [])}

    def point(point_id: str, label: str, values: tuple[float, ...]) -> dict:
        return {
            "id": point_id,
            "label": label,
            "objective_values": {
                spec.id: values[index] for index, spec in enumerate(result.objectives)
            },
        }

    return {
        "run_id": run_id,
        "method": result.method,
        "antiutopian_kind": "nadir",
        "objectives": [
            {
                "id": spec.id,
                "name": catalog[spec.id].get("name"),
                "unit": catalog[spec.id].get("unit"),
                "direction": spec.direction,
            }
            for spec in result.objectives
        ],
        "utopian": point("utopian", "Solução utópica", result.utopian),
        "antiutopian": point("antiutopian", "Solução antiutópica", result.nadir),
        "distance": {
            "metric": "euclidean",
            "label": "Distância euclidiana normalizada",
            "space": "normalized_objectives",
            "note": "Cada objetivo vai de 0 no utópico a 1 no nadir.",
        },
        "note": (
            "Estimativa a partir das soluções mapeadas. "
            "A solução antiutópica é o nadir da fronteira, não o pior ponto da região viável."
        ),
        "warnings": [{"code": warning.code, "message": warning.message} for warning in result.warnings],
    }


@runs_blueprint.get("/runs/<run_id>/hypervolume")
def get_run_hypervolume(run_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            return _error("run_not_found", "A execução solicitada não existe.", 404)
        if run.status != "completed":
            return _error(
                "run_not_completed",
                "O hipervolume só está disponível após a conclusão da execução.",
                409,
            )
        instance = session.get(Instance, run.instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância da execução não existe.", 404)
        problem_type = current_app.extensions["paretolab_catalog"].get_problem_type(instance.problem_type_id)
        if problem_type is None:
            return _error(
                "unknown_problem_type",
                "O tipo de problema da instância não está no catálogo.",
                422,
            )
        rows = session.scalars(select(RunSolution).where(RunSolution.run_id == run_id)).all()
        samples = [
            {"round": row.round_index, **(row.objective_values or {})}
            for row in rows
        ]
        try:
            objectives = _reference_objectives(problem_type, rows)
            summary = summarize_run_hypervolume(samples, objectives)
            spread = summarize_run_spread(samples, objectives)
        except ReferencePointError as error:
            details = [{"stage": error.stage}] if error.stage else []
            return _error("hypervolume_unavailable", str(error), 409, details)
        except ValueError as error:
            return _error("invalid_hypervolume", str(error), 422)
        payload = _hypervolume_payload(run.run_id, problem_type, objectives, summary, spread)
    return jsonify(payload), 200


def _hypervolume_payload(
    run_id: str,
    _problem_type: dict,
    objectives: tuple[ObjectiveSpec, ...],
    summary,
    spread,
) -> dict:
    objective_ids = [spec.id for spec in objectives]

    def named(values: tuple[float, ...]) -> dict:
        return {objective_id: values[index] for index, objective_id in enumerate(objective_ids)}

    return {
        "run_id": run_id,
        "reference_shift": summary.reference_shift,
        "space": "normalized_objectives",
        "unit": None,
        "standard_deviation": "sample",
        "nadir": named(summary.nadir),
        "reference_point": named(summary.reference_point),
        "rounds": [
            {
                "round": item.round_index,
                "hypervolume": item.hypervolume,
                "candidate_count": item.candidate_count,
                "distance_to_mean": item.distance_to_mean,
                "spread": spread_item.spread,
            }
            for item, spread_item in zip(summary.rounds, spread.rounds, strict=True)
        ],
        "mean_hypervolume": summary.mean_hypervolume,
        "sample_stdev_hypervolume": summary.sample_stdev_hypervolume,
        "coefficient_of_variation": summary.coefficient_of_variation,
        "mean_candidate_count": summary.mean_candidate_count,
        "mean_spread": spread.mean_spread,
        "sample_stdev_spread": spread.sample_stdev_spread,
        "spread_coefficient_of_variation": spread.coefficient_of_variation,
        "note": (
            "Área adimensional no espaço normalizado: cada objetivo vai de 0 no utópico a 1 no nadir. "
            "A referência é 1,1 vezes o nadir normalizado em cada eixo com faixa positiva, "
            "e vale para todas as rodadas. Faixa nula permanece 0. "
            "O desvio padrão é amostral (n − 1); com uma rodada ele vale 0. "
            "O coeficiente de variação é esse desvio dividido pela média de todas as rodadas; "
            "se a média é 0, o coeficiente não é calculado e o valor é nulo."
        ),
        "spread_note": (
            "O espalhamento Δ é adimensional no mesmo espaço normalizado, de 0 no utópico a 1 no nadir. "
            "Δ = 0 indica distâncias consecutivas iguais e cobertura dos extremos da união das rodadas. "
            "Com menos de duas soluções na fronteira candidata, Δ vale 1. "
            "O desvio padrão é amostral (n − 1); com uma rodada ele vale 0. "
            "O coeficiente de variação é nulo se a média de Δ é 0."
        ),
    }


@runs_blueprint.get("/instances/<instance_id>/quality-evolution")
def get_instance_quality_evolution(instance_id: str):
    engine = current_app.extensions["paretolab_database_engine"]
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if instance is None:
            return _error("instance_not_found", "A instância solicitada não existe.", 404)
        if instance.status == "deleting":
            return _error("instance_unavailable", "A instância está sendo excluída.", 409)
        problem_type = current_app.extensions["paretolab_catalog"].get_problem_type(instance.problem_type_id)
        if problem_type is None:
            return _error(
                "unknown_problem_type",
                "O tipo de problema da instância não está no catálogo.",
                422,
            )
        runs = session.scalars(
            select(Run).where(Run.instance_id == instance_id, Run.status == "completed")
        ).all()
        rows = session.scalars(
            select(RunAttemptSample).where(RunAttemptSample.run_id.in_([run.run_id for run in runs]))
        ).all() if runs else []
        samples_by_run: dict[str, list[RunAttemptSample]] = {}
        for row in rows:
            samples_by_run.setdefault(row.run_id, []).append(row)
        try:
            tracks: list[RunIndicatorTrack] = []
            for run in runs:
                tracks.extend(
                    _quality_tracks(run, samples_by_run.get(run.run_id, []), problem_type)
                )
            curves = aggregate_quality_evolution(tracks)
        except ReferencePointError as error:
            details = [{"stage": error.stage}] if error.stage else []
            return _error("quality_evolution_unavailable", str(error), 409, details)
        except ValueError as error:
            return _error("invalid_quality_evolution", str(error), 422)
        payload = _quality_evolution_payload(
            instance.instance_id,
            problem_type,
            curves,
            _evolution_empty_message(runs, samples_by_run, problem_type, curves),
        )
    return jsonify(payload), 200


def _quality_tracks(
    run: Run,
    rows: list[RunAttemptSample],
    problem_type: dict,
) -> list[RunIndicatorTrack]:
    """Prefix curves for one execution.

    Rows without an attempt index are not read from ``run_solutions``. A run
    that never stored sampling order contributes nothing.
    """

    if not rows:
        return []
    distinct_rounds = {row.round_index for row in rows}
    if is_exact_execution(len(distinct_rounds), _catalog_exact(problem_type, run.algorithm_id)):
        return []
    objectives = _reference_objectives(problem_type, rows)
    measured = measure_run_indicators(
        [
            {"round": row.round_index, "attempt": row.attempt_index, **(row.objective_values or {})}
            for row in rows
        ],
        objectives,
    )
    configuration = configuration_key(run.parameters)
    return [
        RunIndicatorTrack(
            algorithm_id=run.algorithm_id,
            configuration=configuration,
            round_index=series.round_index,
            samples=series.samples,
            exact=False,
        )
        for series in measured
    ]


def _evolution_empty_message(
    runs: list[Run],
    samples_by_run: dict[str, list[RunAttemptSample]],
    problem_type: dict,
    curves: tuple[MeanCurve, ...],
) -> str | None:
    if curves:
        return None
    pending = [
        run
        for run in runs
        if not samples_by_run.get(run.run_id)
        and _catalog_exact(problem_type, run.algorithm_id) is False
    ]
    if not pending:
        return None
    return (
        "As execuções concluídas não guardam a ordem das amostragens. "
        "A curva por prefixo aparece nas próximas execuções."
    )


def _catalog_exact(problem_type: dict, algorithm_id: str) -> bool | None:
    algorithm = next(
        (item for item in problem_type.get("algorithms") or [] if item.get("id") == algorithm_id),
        None,
    )
    if not algorithm:
        return None
    if algorithm.get("exact") is True or algorithm.get("method") == "exact":
        return True
    if algorithm.get("exact") is False or algorithm.get("method") in {"heuristic", "metaheuristic"}:
        return False
    return None


def _quality_evolution_payload(
    instance_id: str,
    problem_type: dict,
    curves: tuple[MeanCurve, ...],
    empty_message: str | None,
) -> dict:
    names = {
        item["id"]: item.get("name")
        for item in problem_type.get("algorithms") or []
        if item.get("id")
    }
    configurations: dict[str, set[tuple[tuple[str, object], ...]]] = {}
    for curve in curves:
        configurations.setdefault(curve.algorithm_id, set()).add(curve.configuration)

    def curve_payload(curve: MeanCurve, value_name: str) -> dict:
        return {
            "algorithm_id": curve.algorithm_id,
            "round": curve.round_index,
            "label": _evolution_label(
                curve,
                names,
                len(configurations.get(curve.algorithm_id, ())) > 1,
            ),
            "points": [
                {
                    "accumulated_samples": stable_number(point.accumulated_samples),
                    "mean": stable_number(getattr(point, value_name)),
                }
                for point in curve.points
            ],
        }

    payload = {
        "instance_id": instance_id,
        "axis": ACCUMULATED_SAMPLES_AXIS,
        "axis_label": "Amostragens acumuladas na rodada",
        "space": "normalized_objectives",
        "hypervolume": {"curves": [curve_payload(curve, "hypervolume") for curve in curves]},
        "spread": {"curves": [curve_payload(curve, "spread") for curve in curves]},
        "note": (
            "Cada curva é uma rodada. O eixo horizontal é o número de amostragens acumuladas "
            "nessa rodada: blocos de 10, e o último ponto é o prefixo completo. "
            "Com menos de 10 amostragens há um único ponto, no total da rodada. "
            "A média junta execuções do mesmo algoritmo e dos mesmos parâmetros, na mesma rodada "
            "e no mesmo tamanho de prefixo, sem contar a semente. "
            "O utópico, o nadir e os extremos do espalhamento são os da execução inteira. "
            "Execuções antigas, sem a ordem das amostragens, não entram neste gráfico."
        ),
    }
    if empty_message:
        payload["empty_message"] = empty_message
    return payload


def _evolution_label(curve: MeanCurve, names: dict[str, object], distinguish_configuration: bool) -> str:
    raw_name = names.get(curve.algorithm_id)
    name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else curve.algorithm_id
    details = _configuration_label(curve.configuration) if distinguish_configuration else ""
    round_label = f"rodada {curve.round_index}"
    if details:
        return f"{name} · {details} · {round_label}"
    return f"{name} · {round_label}"


def _configuration_label(configuration: tuple[tuple[str, object], ...]) -> str:
    params = dict(configuration)
    parts: list[str] = []
    if "iterations" in params:
        parts.append(f"{params['iterations']} amostragens")
    if "repetitions" in params:
        parts.append(f"{params['repetitions']} rodadas")
    for key, value in params.items():
        if key in {"iterations", "repetitions"}:
            continue
        parts.append(f"{key} {value}")
    return " · ".join(parts)


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


def _matrix_value(matrix: tuple[tuple[float, ...], ...] | None, source: object, target: object) -> float | None:
    if matrix is None:
        return None
    try:
        row_index = int(source) - 1
        column_index = int(target) - 1
    except (TypeError, ValueError):
        return None
    if row_index < 0 or column_index < 0 or row_index >= len(matrix):
        return None
    row = matrix[row_index]
    if column_index >= len(row):
        return None
    value = row[column_index]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return float(value)


def route_edges_with_objectives(
    route: list,
    time_matrix: tuple[tuple[float, ...], ...] | None = None,
    distance_matrix: tuple[tuple[float, ...], ...] | None = None,
) -> list[dict[str, int | float]]:
    edges: list[dict[str, int | float]] = []
    for index in range(len(route) - 1):
        source = route[index]
        target = route[index + 1]
        edge: dict[str, int | float] = {"source": source, "target": target}
        time_value = _matrix_value(time_matrix, source, target)
        distance_value = _matrix_value(distance_matrix, source, target)
        if time_value is not None:
            edge["time"] = time_value
        if distance_value is not None:
            edge["distance"] = distance_value
        edges.append(edge)
    return edges


def _optional_instance_matrix(instance_id: str, role: str):
    try:
        from api.routes.instances import _get_instance_matrix

        return _get_instance_matrix(instance_id, role)
    except Exception:
        return None


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
        edges = route_edges_with_objectives(
            route,
            _optional_instance_matrix(solution.instance_id, "time_matrix"),
            _optional_instance_matrix(solution.instance_id, "distance_matrix"),
        )
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

