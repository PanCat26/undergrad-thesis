"""per-user chat model selection

Revision ID: 0007_user_llm
Revises: 0006_rate_counters
Create Date: 2026-06-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_user_llm"
down_revision: str | None = "0006_rate_counters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("llm_model", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("llm_base_url", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("llm_api_key", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "llm_api_key")
    op.drop_column("users", "llm_base_url")
    op.drop_column("users", "llm_model")
