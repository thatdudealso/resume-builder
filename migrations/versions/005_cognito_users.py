"""Add cognito_sub and allow null password_hash for Cognito users.

Revision ID: 005_cognito_users
Revises: 004_default_provider_openai
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_cognito_users"
down_revision: str | None = "004_default_provider_openai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("cognito_sub", sa.String(length=128), nullable=True))
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_users_cognito_sub", table_name="users")
    op.drop_column("users", "cognito_sub")
