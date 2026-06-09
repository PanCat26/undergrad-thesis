"""source citation metadata

Revision ID: 0005_source_citation
Revises: 0004_chat
Create Date: 2026-06-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_source_citation"
down_revision: str | None = "0004_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("cite_key", sa.String(length=255), nullable=True))
    op.add_column("sources", sa.Column("bibtex", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "bibtex")
    op.drop_column("sources", "cite_key")
