from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.postgres.base import Base


class RunRobustnessAnalysis(Base):
    __tablename__ = "run_robustness_analyses"

    run_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
