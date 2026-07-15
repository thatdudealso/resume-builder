"""Change agent_runs.llm_provider default from huggingface to openai.

Revision ID: 004_default_provider_openai
Revises: 003_resume_style_metadata
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_default_provider_openai"
down_revision: str | None = "003_resume_style_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "agent_runs",
        "llm_provider",
        existing_type=sa.String(32),
        server_default="openai",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_runs",
        "llm_provider",
        existing_type=sa.String(32),
        server_default="huggingface",
    )
