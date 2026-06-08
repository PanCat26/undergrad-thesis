"""sources

Revision ID: 0003_sources
Revises: 0002_project_files
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sources"
down_revision: str | None = "0002_project_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ext", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processing"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sources_project_id", "sources", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_project_id", table_name="sources")
    op.drop_table("sources")
