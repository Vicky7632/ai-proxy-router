import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class CacheOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"


class RequestLog(Base):
    __tablename__ = "requests_log"

    __table_args__ = (
        CheckConstraint(
            "redis_cache_status IS NULL OR redis_cache_status IN ('hit', 'miss')",
            name="ck_requests_log_redis_cache_status",
        ),
        CheckConstraint(
            "semantic_cache_status IS NULL OR semantic_cache_status IN ('hit', 'miss')",
            name="ck_requests_log_semantic_cache_status",
        ),
        Index("ix_requests_log_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=True)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    cache_hit = Column(Boolean, default=False)
    redis_cache_status = Column(String(4), nullable=True)
    semantic_cache_status = Column(String(4), nullable=True)
    provider_called = Column(Boolean, nullable=True)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
