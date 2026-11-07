from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.postgres.base import Base


class RunSolution(Base):
    __tablename__ = "run_solutions"

    solution_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    objective_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    route: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    dominance: Mapped[str] = mapped_column(String(32), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class RunAttemptSample(Base):
    """One sampling attempt, in the order needed to rebuild round prefixes.

    The mapped frontier stays in ``run_solutions``. These rows keep the
    attempt index and the objectives of every call, including repeated routes.
    """

    __tablename__ = "run_attempt_samples"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "round_index",
            "attempt_index",
            name="uq_run_attempt_samples_position",
        ),
    )

    sample_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    objective_values: Mapped[dict] = mapped_column(JSON, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_read: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
