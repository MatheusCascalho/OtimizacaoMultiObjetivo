import logging
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.settings import Settings
from infrastructure.persistence.postgres.models import (
    Instance,
    InstanceFile,
    Notification,
    Run,
    RunSolution,
    TemporaryUpload,
)
from infrastructure.object_storage.s3.client import create_s3_client
from infrastructure.object_storage.s3.storage import S3ObjectStorage
from infrastructure.persistence.postgres.database import create_engine
from monoobjective_algorithms.interfaces import SolveRequest
from monoobjective_algorithms.tsp.heuristics import NeuroLKH
from multiobjective_algorithms.dominance import non_dominated_mask
from optimization_problems.tsp import TSPInstance
from workflow_instance.domain.frontier_sampling import (
    DEFAULT_ITERATIONS,
    FRONTIER_REPETITIONS,
    round_seed,
    total_attempts,
)
from workflow_instance.domain.matrices import parse_matrix_csv


logger = logging.getLogger(__name__)


@shared_task(name="worker.ping")
def ping_worker() -> str:
    return "pong"


def purge_expired_uploads(
    session: Session,
    object_storage: S3ObjectStorage,
    now: datetime,
) -> int:
    expired_uploads = session.scalars(
        select(TemporaryUpload)
        .where(
            TemporaryUpload.expires_at <= now,
            TemporaryUpload.consumed_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    ).all()
    deleted_count = 0
    for upload in expired_uploads:
        try:
            object_storage.delete(upload.object_key)
        except (BotoCoreError, ClientError):
            logger.exception("Could not delete expired upload object %s", upload.id)
            continue
        session.delete(upload)
        deleted_count += 1
    session.commit()
    return deleted_count


def reconcile_orphaned_objects(
    session: Session,
    object_storage: S3ObjectStorage,
    now: datetime,
    minimum_age: timedelta = timedelta(hours=1),
) -> int:
    known_keys = set(session.scalars(select(TemporaryUpload.object_key)).all())
    known_keys.update(session.scalars(select(InstanceFile.object_key)).all())
    cutoff = now - minimum_age
    deleted_count = 0
    for prefix in ("temporary-uploads/", "instance-files/"):
        for item in object_storage.list_objects(prefix):
            key = item.get("key")
            last_modified = item.get("last_modified")
            if not isinstance(key, str) or key in known_keys or not isinstance(last_modified, datetime):
                continue
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=UTC)
            if last_modified > cutoff:
                continue
            try:
                object_storage.delete(key)
            except (BotoCoreError, ClientError):
                logger.exception("Could not delete orphaned object %s", key)
                continue
            deleted_count += 1
    return deleted_count


def _set_instance_status(session: Session, instance_id: str, status: str, updated_at: datetime) -> None:
    instance = session.get(Instance, instance_id)
    if instance is not None:
        instance.status = status
        instance.updated_at = updated_at


@shared_task(name="worker.cleanup_expired_uploads")
def cleanup_expired_uploads() -> int:
    settings = Settings()
    engine = create_engine(settings)
    object_storage = S3ObjectStorage(
        create_s3_client(settings),
        settings.s3_bucket,
    )
    try:
        with Session(engine) as session:
            return purge_expired_uploads(session, object_storage, datetime.now(UTC))
    finally:
        engine.dispose()


@shared_task(name="worker.reconcile_orphaned_objects")
def cleanup_orphaned_objects() -> int:
    settings = Settings()
    engine = create_engine(settings)
    object_storage = S3ObjectStorage(create_s3_client(settings), settings.s3_bucket)
    try:
        with Session(engine) as session:
            return reconcile_orphaned_objects(
                session,
                object_storage,
                datetime.now(UTC),
                timedelta(seconds=settings.temporary_upload_ttl_seconds),
            )
    finally:
        engine.dispose()


@shared_task(name="worker.execute_run")
def execute_run(run_id: str) -> str:
    settings = Settings()
    engine = create_engine(settings)
    object_storage = S3ObjectStorage(
        create_s3_client(settings),
        settings.s3_bucket,
    )
    try:
        return execute_run_with_dependencies(run_id, engine, object_storage)
    finally:
        engine.dispose()


def _positive_int(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return default
    return value


def _neuro_lkh_weight(run_parameters: dict, completed: int, total: int) -> float:
    if "weight" in run_parameters:
        return run_parameters["weight"]
    if total <= 1:
        return 0.5
    return (completed - 1) / (total - 1)


def execute_run_with_dependencies(run_id: str, engine, object_storage) -> str:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None or run.status in {"running", "completed", "cancelled", "failed"}:
            return run_id
        if run.status == "cancel_requested":
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)
            run.updated_at = run.finished_at
            _set_instance_status(session, run.instance_id, "cancelled", run.updated_at)
            session.commit()
            return run_id

        instance = session.get(Instance, run.instance_id)
        files = session.scalars(
            select(InstanceFile).where(InstanceFile.instance_id == run.instance_id)
        ).all()
        run_parameters = dict(run.parameters or {})
        instance_id = run.instance_id
        iterations = _positive_int(run_parameters.get("iterations"), DEFAULT_ITERATIONS)
        repetitions = _positive_int(run_parameters.get("repetitions"), FRONTIER_REPETITIONS)
        total = total_attempts(iterations, repetitions)
        if instance is None or len(files) != 2:
            run.status = "failed"
            run.error_message = "Os dados de entrada da instância não estão disponíveis."
            run.finished_at = datetime.now(UTC)
            run.updated_at = run.finished_at
            _set_instance_status(session, run.instance_id, "failed", run.updated_at)
            session.commit()
            return run_id
        file_keys = {row.role: row.object_key for row in files}
        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.updated_at = run.started_at
        _set_instance_status(session, run.instance_id, "running", run.updated_at)
        session.commit()

    try:
        time_matrix = parse_matrix_csv(object_storage.get(file_keys["time_matrix"]), file_keys["time_matrix"])
        distance_matrix = parse_matrix_csv(
            object_storage.get(file_keys["distance_matrix"]), file_keys["distance_matrix"]
        )
        instance_data = TSPInstance(time_matrix=time_matrix, distance_matrix=distance_matrix)
        seed = run_parameters.get("seed")
        base_seed = seed if isinstance(seed, int) and not isinstance(seed, bool) else None
        solver = NeuroLKH(seed=base_seed)
        progress_interval = max(1, ceil(total / 20))
        sampled_rounds: list[list[dict]] = []

        for round_index in range(1, repetitions + 1):
            unique_solutions: dict[tuple[int, ...], dict] = {}
            attempt_seed = round_seed(base_seed, round_index) if base_seed is not None else None
            for attempt in range(1, iterations + 1):
                completed = (round_index - 1) * iterations + attempt
                with Session(engine) as session:
                    current_run = session.get(Run, run_id)
                    if current_run is None or current_run.status == "cancel_requested":
                        if current_run is not None:
                            current_run.status = "cancelled"
                            current_run.finished_at = datetime.now(UTC)
                            current_run.updated_at = current_run.finished_at
                            _set_instance_status(session, instance_id, "cancelled", current_run.updated_at)
                            session.commit()
                        return run_id

                parameters = {"weight": _neuro_lkh_weight(run_parameters, attempt, iterations)}
                if attempt_seed is not None:
                    parameters["seed"] = attempt_seed
                if "lkh_trials" in run_parameters:
                    parameters["lkh_trials"] = run_parameters["lkh_trials"]
                result = solver.solve(
                    instance_data,
                    SolveRequest(objective="time", parameters=parameters),
                )
                if result.status not in {"optimal", "feasible"} or result.solution is None:
                    raise RuntimeError("A heurística não retornou uma rota factível.")
                unique_solutions.setdefault(
                    tuple(result.solution.route),
                    {
                        "route": list(result.solution.route),
                        "objective_values": dict(result.objective_values),
                    },
                )

                if completed % progress_interval == 0 or completed == total:
                    with Session(engine) as session:
                        current_run = session.get(Run, run_id)
                        if current_run is None or current_run.status == "cancel_requested":
                            if current_run is not None:
                                current_run.status = "cancelled"
                                current_run.finished_at = datetime.now(UTC)
                                current_run.updated_at = current_run.finished_at
                                _set_instance_status(session, instance_id, "cancelled", current_run.updated_at)
                                session.commit()
                            return run_id
                        current_run.progress = {
                            "completed": completed,
                            "total": total,
                            "percent": 100 if completed == total else int((completed / total) * 100),
                        }
                        current_run.updated_at = datetime.now(UTC)
                        session.commit()

            round_solutions = list(unique_solutions.values())
            mask = non_dominated_mask(
                [
                    [solution["objective_values"]["time"], solution["objective_values"]["distance"]]
                    for solution in round_solutions
                ],
                ("minimize", "minimize"),
            )
            for solution, is_non_dominated in zip(round_solutions, mask):
                solution["dominance"] = "non_dominated" if is_non_dominated else "dominated"
                solution["round_index"] = round_index
            sampled_rounds.append(round_solutions)

        solutions = [solution for round_solutions in sampled_rounds for solution in round_solutions]
        now = datetime.now(UTC)
        with Session(engine) as session:
            current_run = session.get(Run, run_id)
            if current_run is None or current_run.status == "cancel_requested":
                if current_run is not None:
                    current_run.status = "cancelled"
                    current_run.finished_at = now
                    current_run.updated_at = now
                    _set_instance_status(session, instance_id, "cancelled", now)
                    session.commit()
                return run_id

            for solution in solutions:
                session.add(
                    RunSolution(
                        solution_id=f"sol_{uuid4().hex}",
                        run_id=run_id,
                        instance_id=instance_id,
                        objective_values=solution["objective_values"],
                        route=solution["route"],
                        dominance=solution["dominance"],
                        round_index=solution["round_index"],
                        created_at=now,
                    )
                )
            current_run.status = "completed"
            current_run.progress = {"completed": total, "total": total, "percent": 100}
            current_run.finished_at = now
            current_run.updated_at = now
            _set_instance_status(session, instance_id, "completed", now)
            session.add(
                Notification(
                    notification_id=f"notif_{uuid4().hex}",
                    instance_id=instance_id,
                    run_id=run_id,
                    title="Execução concluída",
                    message=(
                        f"A execução gerou {len(solutions)} soluções únicas em {repetitions} rodadas."
                    ),
                    is_read=False,
                    created_at=now,
                )
            )
            session.commit()
        return run_id
    except Exception:
        logger.exception("Run %s failed during optimization", run_id)
        with Session(engine) as session:
            failed_run = session.get(Run, run_id)
            if failed_run is not None and failed_run.status not in {"cancelled", "completed"}:
                failed_run.status = "failed"
                failed_run.error_message = "A execução falhou durante o processamento."
                failed_run.finished_at = datetime.now(UTC)
                failed_run.updated_at = failed_run.finished_at
                _set_instance_status(session, failed_run.instance_id, "failed", failed_run.updated_at)
                session.commit()
        return run_id
