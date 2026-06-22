"""Add llm_provider to agent_runs.

Revision ID: 002_llm_provider
Revises: 001_initial
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_llm_provider"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("llm_provider", sa.String(32), server_default="huggingface", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "llm_provider")
