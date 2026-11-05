"""Store the wall time of each completed sampling attempt.

Revision ID: 0006_solution_timings
Revises: 0005_solution_rounds
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_solution_timings"
down_revision: str | None = "0005_solution_rounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("solution_timings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "solution_timings")
