from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from infrastructure.persistence.postgres.base import Base
from infrastructure.persistence.postgres.models import TemporaryUpload
from worker.tasks import purge_expired_uploads


class FakeObjectStorage:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


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