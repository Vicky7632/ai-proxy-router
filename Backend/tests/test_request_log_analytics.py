from uuid import uuid4

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.models import CacheOutcome, RequestLog


def test_request_log_exposes_structured_cache_analytics_fields():
    request_log = RequestLog(
        api_key_id=uuid4(),
        model="model-a",
        status="200",
        redis_cache_status=CacheOutcome.MISS,
        semantic_cache_status=CacheOutcome.ERROR,
        provider_called=False,
        latency_ms=12,
    )

    assert request_log.id is None
    assert request_log.redis_cache_status == CacheOutcome.MISS
    assert request_log.semantic_cache_status == CacheOutcome.ERROR
    assert "error" in str(next(
        constraint.sqltext
        for constraint in RequestLog.__table__.constraints
        if constraint.name == "ck_requests_log_semantic_cache_status"
    ))
    assert request_log.provider_called is False
    assert RequestLog.model.property.columns[0].name == "model"
    assert RequestLog.latency_ms.property.columns[0].name == "latency_ms"
    assert RequestLog.created_at.property.columns[0].name == "created_at"


def test_request_log_analytics_constraints_and_time_index_compile_for_postgres():
    constraints = [
        constraint
        for constraint in RequestLog.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert {constraint.name for constraint in constraints} >= {
        "ck_requests_log_redis_cache_status",
        "ck_requests_log_semantic_cache_status",
    }
    assert any(
        index.name == "ix_requests_log_created_at"
        for index in RequestLog.__table__.indexes
    )
    create_table_statement = str(
        CreateTable(RequestLog.__table__).compile(dialect=postgresql.dialect())
    )
    assert "redis_cache_status VARCHAR(5)" in create_table_statement
    assert "semantic_cache_status VARCHAR(5)" in create_table_statement
    assert "provider_called BOOLEAN" in create_table_statement
