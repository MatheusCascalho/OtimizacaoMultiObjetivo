"""Store each sampling attempt so round prefixes can be rebuilt.

Revision ID: 0007_run_attempt_samples
Revises: 0006_solution_timings
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_run_attempt_samples"
down_revision: str | None = "0006_solution_timings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_attempt_samples",
        sa.Column("sample_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("objective_values", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("sample_id"),
        sa.UniqueConstraint(
            "run_id",
            "round_index",
            "attempt_index",
            name="uq_run_attempt_samples_position",
        ),
    )
    op.create_index("ix_run_attempt_samples_run_id", "run_attempt_samples", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_attempt_samples_run_id", table_name="run_attempt_samples")
    op.drop_table("run_attempt_samples")
