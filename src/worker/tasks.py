import logging
from datetime import UTC, datetime

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.settings import Settings
from infrastructure.object_storage.s3.client import create_s3_client
from infrastructure.object_storage.s3.storage import S3ObjectStorage
from infrastructure.persistence.postgres.database import create_engine
from infrastructure.persistence.postgres.models import Run, TemporaryUpload


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


@shared_task(name="worker.execute_run")
def execute_run(run_id: str) -> str:
    settings = Settings()
    engine = create_engine(settings)
    try:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                return run_id

            total = max(int((run.progress or {}).get("total", 0) or 1), 1)
            now = datetime.now(UTC)
            run.status = "running"
            run.started_at = now
            run.updated_at = now
            session.commit()

            for completed in range(1, total + 1):
                if run.status == "cancel_requested":
                    run.status = "cancelled"
                    run.finished_at = datetime.now(UTC)
                    run.updated_at = datetime.now(UTC)
                    session.commit()
                    return run_id

                run.progress = {"completed": completed, "total": total, "percent": round((completed / total) * 100, 2)}
                run.updated_at = datetime.now(UTC)
                session.commit()

            run.status = "completed"
            run.progress = {"completed": total, "total": total, "percent": 100}
            run.finished_at = datetime.now(UTC)
            run.updated_at = datetime.now(UTC)
            session.commit()
            return run_id
    finally:
        engine.dispose()
