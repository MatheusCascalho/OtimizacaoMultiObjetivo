"""Add instance metadata and linked uploads.

Revision ID: 0003_instances
Revises: 0002_temporary_uploads
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_instances"
down_revision: str | None = "0002_temporary_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instances",
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("problem_type_id", sa.String(length=120), nullable=False),
        sa.Column("catalog_version", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("instance_id"),
    )
    op.create_table(
        "instance_files",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("instance_id", sa.String(length=40), nullable=False),
        sa.Column("upload_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "role", name="uq_instance_files_instance_role"),
    )


def downgrade() -> None:
    op.drop_table("instance_files")
    op.drop_table("instances")
