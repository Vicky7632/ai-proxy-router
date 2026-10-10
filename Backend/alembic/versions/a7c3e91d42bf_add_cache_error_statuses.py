"""allow cache lookup errors in request analytics"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c3e91d42bf"
down_revision: Union[str, None] = "10d975a9f591"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.alter_column(
        "requests_log",
        "redis_cache_status",
        existing_type=sa.String(length=4),
        type_=sa.String(length=5),
        existing_nullable=True,
    )
    op.alter_column(
        "requests_log",
        "semantic_cache_status",
        existing_type=sa.String(length=4),
        type_=sa.String(length=5),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "ck_requests_log_redis_cache_status",
        "requests_log",
        "redis_cache_status IS NULL OR redis_cache_status IN ('hit', 'miss', 'error')",
    )
    op.create_check_constraint(
        "ck_requests_log_semantic_cache_status",
        "requests_log",
        "semantic_cache_status IS NULL OR semantic_cache_status IN ('hit', 'miss', 'error')",
    )


def downgrade() -> None:
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
    op.execute(
        "UPDATE requests_log SET redis_cache_status = NULL "
        "WHERE redis_cache_status = 'error'"
    )
    op.execute(
        "UPDATE requests_log SET semantic_cache_status = NULL "
        "WHERE semantic_cache_status = 'error'"
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
    op.alter_column(
        "requests_log",
        "semantic_cache_status",
        existing_type=sa.String(length=5),
        type_=sa.String(length=4),
        existing_nullable=True,
    )
    op.alter_column(
        "requests_log",
        "redis_cache_status",
        existing_type=sa.String(length=5),
        type_=sa.String(length=4),
        existing_nullable=True,
    )
