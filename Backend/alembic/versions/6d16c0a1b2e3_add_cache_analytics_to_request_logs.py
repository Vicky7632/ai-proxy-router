"""add cache analytics fields to request logs

Revision ID: 6d16c0a1b2e3
Revises: 0d5e0348e0ec
Create Date: 2026-10-02 16:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6d16c0a1b2e3"
down_revision: Union[str, None] = "0d5e0348e0ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "requests_log",
        sa.Column("redis_cache_status", sa.String(length=4), nullable=True),
    )
    op.add_column(
        "requests_log",
        sa.Column("semantic_cache_status", sa.String(length=4), nullable=True),
    )
    op.add_column(
        "requests_log",
        sa.Column("provider_called", sa.Boolean(), nullable=True),
    )
    op.create_check_constraint(
        "ck_requests_log_redis_cache_status",
        "requests_log",
        "redis_cache_status IS NULL OR redis_cache_status IN ('hit', 'miss')",
    )
    op.create_check_constraint(
        "ck_requests_log_semantic_cache_status",
        "requests_log",
        "semantic_cache_status IS NULL OR semantic_cache_status IN ('hit', 'miss')",
    )
    op.create_index(
        "ix_requests_log_created_at",
        "requests_log",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_requests_log_created_at", table_name="requests_log")
    op.drop_constraint(
        "ck_requests_log_semantic_cache_status",
        "requests_log",
        type_="check",
    )
    op.drop_constraint(
        "ck_requests_log_redis_cache_status",
        "requests_log",
        type_="check",
    )
    op.drop_column("requests_log", "provider_called")
    op.drop_column("requests_log", "semantic_cache_status")
    op.drop_column("requests_log", "redis_cache_status")
