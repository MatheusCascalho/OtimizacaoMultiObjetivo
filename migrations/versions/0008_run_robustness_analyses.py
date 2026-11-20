"""Persist robustness and multi-criteria analyses per run.

Revision ID: 0008_run_robustness_analyses
Revises: 0007_run_attempt_samples
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_run_robustness_analyses"
down_revision: str | None = "0007_run_attempt_samples"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_robustness_analyses",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_run_robustness_analyses_instance_id",
        "run_robustness_analyses",
        ["instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_robustness_analyses_instance_id", table_name="run_robustness_analyses")
    op.drop_table("run_robustness_analyses")
