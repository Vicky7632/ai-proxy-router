"""add prompt cache table

Revision ID: 10d975a9f591
Revises: 6d16c0a1b2e3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "10d975a9f591"
down_revision: Union[str, None] = "6d16c0a1b2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("response", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("prompt_cache")
