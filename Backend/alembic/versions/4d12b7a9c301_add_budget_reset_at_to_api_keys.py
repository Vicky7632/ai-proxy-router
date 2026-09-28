"""add budget reset timestamp to API keys

Revision ID: 4d12b7a9c301
Revises: 9f90b035d52e
Create Date: 2026-09-28 17:24:36
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d12b7a9c301"
down_revision: Union[str, None] = "9f90b035d52e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("budget_reset_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "budget_reset_at")
