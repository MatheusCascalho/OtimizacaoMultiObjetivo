"""Add run lifecycle, solutions, notifications, and persisted city layouts.

Revision ID: 0004_runs_results
Revises: 0003_instances
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_runs_results"
down_revision: str | None = "0003_instances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("algorithm_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_runs_instance_id", "runs", ["instance_id"])
    op.create_index("ix_runs_idempotency_key", "runs", ["idempotency_key"])

    op.create_table(
        "run_solutions",
        sa.Column("solution_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("objective_values", sa.JSON(), nullable=False),
        sa.Column("route", sa.JSON(), nullable=False),
        sa.Column("dominance", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("solution_id"),
    )
    op.create_index("ix_run_solutions_run_id", "run_solutions", ["run_id"])
    op.create_index("ix_run_solutions_instance_id", "run_solutions", ["instance_id"])

    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("is_read", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_index("ix_notifications_instance_id", "notifications", ["instance_id"])
    op.create_index("ix_notifications_run_id", "notifications", ["run_id"])

    op.create_table(
        "city_layouts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("city_index", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "city_index", name="uq_city_layouts_instance_city"),
    )


def downgrade() -> None:
    op.drop_table("city_layouts")
    op.drop_index("ix_notifications_run_id", table_name="notifications")
    op.drop_index("ix_notifications_instance_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_run_solutions_instance_id", table_name="run_solutions")
    op.drop_index("ix_run_solutions_run_id", table_name="run_solutions")
    op.drop_table("run_solutions")
    op.drop_index("ix_runs_idempotency_key", table_name="runs")
    op.drop_index("ix_runs_instance_id", table_name="runs")
    op.drop_table("runs")