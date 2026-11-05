from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
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
