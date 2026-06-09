"""rate counters

Revision ID: 0006_rate_counters
Revises: 0005_source_citation
Create Date: 2026-06-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_rate_counters"
down_revision: str | None = "0005_source_citation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_counters",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_counters_expires_at", "rate_counters", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_counters_expires_at", table_name="rate_counters")
    op.drop_table("rate_counters")
