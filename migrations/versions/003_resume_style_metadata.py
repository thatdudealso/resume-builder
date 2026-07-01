"""Add style_metadata to master_resumes.

Revision ID: 003_resume_style_metadata
Revises: 002_llm_provider
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_resume_style_metadata"
down_revision: str | None = "002_llm_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "master_resumes",
        sa.Column(
            "style_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("master_resumes", "style_metadata")
