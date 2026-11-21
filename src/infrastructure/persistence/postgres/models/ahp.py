from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.postgres.base import Base


class RunAHPAnalysis(Base):
    __tablename__ = "run_ahp_analyses"

    run_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    instance_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    judgments: Mapped[dict] = mapped_column(JSON, nullable=False)
    criteria_matrix: Mapped[list] = mapped_column(JSON, nullable=False)
    criteria_weights: Mapped[dict] = mapped_column(JSON, nullable=False)
    consistency: Mapped[dict] = mapped_column(JSON, nullable=False)
    ranking: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
