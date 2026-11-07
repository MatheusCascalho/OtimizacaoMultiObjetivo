"""Store the sampling round of each persisted solution.

Revision ID: 0005_solution_rounds
Revises: 0004_runs_results
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_solution_rounds"
down_revision: str | None = "0004_runs_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_solutions",
        sa.Column("round_index", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("run_solutions", "round_index")
