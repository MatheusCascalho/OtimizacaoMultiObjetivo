"""Persist AHP decisions and rankings per run.

Revision ID: 0009_run_ahp_analyses
Revises: 0008_run_robustness_analyses
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_run_ahp_analyses"
down_revision: str | None = "0008_run_robustness_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_ahp_analyses",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("judgments", sa.JSON(), nullable=False),
        sa.Column("criteria_matrix", sa.JSON(), nullable=False),
        sa.Column("criteria_weights", sa.JSON(), nullable=False),
        sa.Column("consistency", sa.JSON(), nullable=False),
        sa.Column("ranking", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_run_ahp_analyses_instance_id",
        "run_ahp_analyses",
        ["instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_ahp_analyses_instance_id", table_name="run_ahp_analyses")
    op.drop_table("run_ahp_analyses")
