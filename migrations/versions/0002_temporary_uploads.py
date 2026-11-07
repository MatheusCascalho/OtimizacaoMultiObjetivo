"""Add temporary uploads.

Revision ID: 0002_temporary_uploads
Revises: 0001_initial
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_temporary_uploads"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "temporary_uploads",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("problem_type_id", sa.String(length=100), nullable=False),
        sa.Column("catalog_version", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_temporary_uploads_object_key"),
    )
    op.create_index(
        "ix_temporary_uploads_expires_at",
        "temporary_uploads",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_temporary_uploads_expires_at", table_name="temporary_uploads")
    op.drop_table("temporary_uploads")