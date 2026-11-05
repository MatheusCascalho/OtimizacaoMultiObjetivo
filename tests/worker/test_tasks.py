from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import (
    Instance,
    InstanceFile,
    Notification,
    Run,
    RunSolution,
    TemporaryUpload,
)
from monoobjective_algorithms.interfaces import SolveResult
from monoobjective_algorithms.tsp.heuristics import TSPSolution
from worker.tasks import execute_run_with_dependencies, purge_expired_uploads, reconcile_orphaned_objects


class _RecordingNeuroLKH:
    requests = []

    def __init__(self, seed=None, **kwargs) -> None:
        self.seed = seed

    def solve(self, instance, request):
        _RecordingNeuroLKH.requests.append(request)
        route = (1, 2, 3, 1) if len(_RecordingNeuroLKH.requests) % 2 else (1, 3, 2, 1)
        time_cost = sum(
            instance.time_matrix[source - 1][target - 1]
            for source, target in zip(route, route[1:])
        )
        distance_cost = sum(
            instance.distance_matrix[source - 1][target - 1]
            for source, target in zip(route, route[1:])
        )
        return SolveResult(
            status="feasible",
            solution=TSPSolution(route=route),
            objective_values={"time": time_cost, "distance": distance_cost},
        )


class FakeObjectStorage:
    def __init__(
        self,
        objects: dict[str, bytes] | None = None,
        listed_objects: list[dict[str, object]] | None = None,
    ) -> None:
        self.deleted_keys: list[str] = []
        self.objects = objects or {}
        self.listed_objects = listed_objects or []

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def list_objects(self, prefix: str) -> list[dict[str, object]]:
        return [item for item in self.listed_objects if str(item["key"]).startswith(prefix)]


def create_upload(
    upload_id: str,
    expires_at: datetime,
    consumed_at: datetime | None = None,
) -> TemporaryUpload:
    return TemporaryUpload(
        id=upload_id,
        problem_type_id="tsp-time-distance",
        catalog_version="1.0.0",
        role="time_matrix",
        original_filename=f"{upload_id}.csv",
        object_key=f"temporary-uploads/{upload_id}",
        size_bytes=8,
        sha256="a" * 64,
        content_type="text/csv",
        node_count=2,
        status="valid",
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        consumed_at=consumed_at,
    )


def test_purge_removes_only_expired_unconsumed_uploads() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    object_storage = FakeObjectStorage()
    with Session(engine) as session:
        session.add_all(
            [
                create_upload("expired", now - timedelta(seconds=1)),
                create_upload("current", now + timedelta(minutes=5)),
                create_upload(
                    "consumed",
                    now - timedelta(seconds=1),
                    consumed_at=now - timedelta(minutes=1),
                ),
            ]
        )
        session.commit()

        deleted_count = purge_expired_uploads(session, object_storage, now)
        remaining_ids = set(session.scalars(select(TemporaryUpload.id)).all())

    engine.dispose()
    assert deleted_count == 1
    assert object_storage.deleted_keys == ["temporary-uploads/expired"]
    assert remaining_ids == {"current", "consumed"}


def test_execute_run_persists_unique_solutions_and_completion_notification() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    object_storage = FakeObjectStorage(
        {
            "instances/time.csv": b"0,1,8\n7,0,3\n4,6,0\n",
            "instances/distance.csv": b"0,5,9\n8,0,2\n3,7,0\n",
        }
    )
    with Session(engine) as session:
        session.add(
            Instance(
                instance_id="inst_worker_1",
                problem_type_id="tsp-time-distance",
                catalog_version="1.0.0",
                name="TSP de teste",
                status="ready",
                configuration={"algorithm_id": "random-heuristic"},
                node_count=3,
            )
        )
        session.add_all(
            [
                InstanceFile(
                    id="if_time",
                    instance_id="inst_worker_1",
                    upload_id="upl_time",
                    role="time_matrix",
                    object_key="instances/time.csv",
                    sha256="a" * 64,
                    size_bytes=20,
                ),
                InstanceFile(
                    id="if_distance",
                    instance_id="inst_worker_1",
                    upload_id="upl_distance",
                    role="distance_matrix",
                    object_key="instances/distance.csv",
                    sha256="b" * 64,
                    size_bytes=20,
                ),
            ]
        )
        session.add(
            Run(
                run_id="run_worker_1",
                instance_id="inst_worker_1",
                algorithm_id="random-heuristic",
                status="queued",
                parameters={"iterations": 20, "seed": 7},
                progress={"completed": 0, "total": 20, "percent": 0},
                idempotency_key="worker-test",
            )
        )
        session.commit()

    _RecordingNeuroLKH.requests = []
    with patch("worker.tasks.NeuroLKH", _RecordingNeuroLKH):
        assert execute_run_with_dependencies("run_worker_1", engine, object_storage) == "run_worker_1"
    weights = [request.parameters["weight"] for request in _RecordingNeuroLKH.requests]
    assert weights[0] == 0
    assert weights[-1] == 1
    assert len(weights) == 20

    with Session(engine) as session:
        run = session.get(Run, "run_worker_1")
        solutions = session.scalars(
            select(RunSolution).where(RunSolution.run_id == "run_worker_1")
        ).all()
        notifications = session.scalars(
            select(Notification).where(Notification.run_id == "run_worker_1")
        ).all()

    engine.dispose()
    assert run is not None
    assert run.status == "completed"
    assert run.progress == {"completed": 20, "total": 20, "percent": 100}
    assert 1 <= len(solutions) <= 2
    assert all(solution.route[0] == solution.route[-1] == 1 for solution in solutions)
    assert {solution.dominance for solution in solutions} <= {"non_dominated", "dominated"}
    assert len(notifications) == 1
    assert notifications[0].instance_id == "inst_worker_1"


def test_reconcile_deletes_only_old_unreferenced_objects() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    object_storage = FakeObjectStorage(
        listed_objects=[
            {"key": "temporary-uploads/known", "last_modified": now - timedelta(hours=2)},
            {"key": "temporary-uploads/orphan", "last_modified": now - timedelta(hours=2)},
            {"key": "temporary-uploads/recent", "last_modified": now - timedelta(minutes=2)},
        ]
    )
    with Session(engine) as session:
        session.add(create_upload("known", now + timedelta(hours=1)))
        session.commit()
        deleted_count = reconcile_orphaned_objects(
            session,
            object_storage,
            now,
            minimum_age=timedelta(hours=1),
        )

    engine.dispose()
    assert deleted_count == 1
    assert object_storage.deleted_keys == ["temporary-uploads/orphan"]