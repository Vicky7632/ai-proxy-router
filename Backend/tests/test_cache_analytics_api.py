import hashlib
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.api_key import APIKey
from app.db.models.request_log import RequestLog
from app.db.models.user import User
from app.db.session import get_db
from app.main import app


@compiles(UUID, "sqlite")
def compile_postgresql_uuid_for_sqlite(type_, compiler, **kwargs):
    return "CHAR(32)"


@pytest.fixture
def analytics_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, APIKey.__table__, RequestLog.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    user = User(
        id=uuid.uuid4(),
        email="analytics@example.test",
        hashed_password="not-used",
    )
    raw_api_key = "analytics-test-key"
    api_key = APIKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(raw_api_key.encode()).hexdigest(),
        is_active=True,
    )
    db.add_all([user, api_key])
    db.commit()

    def override_get_db():
        request_db = session_factory()
        try:
            yield request_db
        finally:
            request_db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, db, raw_api_key, api_key.id
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def add_request(db, api_key_id, **analytics_fields):
    db.add(
        RequestLog(
            api_key_id=api_key_id,
            model="test-model",
            status="200",
            **analytics_fields,
        )
    )
    db.commit()


def get_analytics(client, api_key):
    return client.get(
        "/v1/analytics/cache",
        headers={"Authorization": f"Bearer {api_key}"},
    )


def test_empty_request_logs_return_zero_counts_and_rate(analytics_client):
    client, _, raw_api_key, _ = analytics_client

    response = get_analytics(client, raw_api_key)

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 0,
        "redis_hits": 0,
        "redis_misses": 0,
        "semantic_hits": 0,
        "semantic_misses": 0,
        "provider_calls": 0,
        "cache_hits": 0,
        "cache_hit_rate": 0.0,
    }


def test_mixed_cache_outcomes_do_not_count_semantic_hit_as_provider_call(
    analytics_client,
):
    client, db, raw_api_key, api_key_id = analytics_client
    add_request(
        db,
        api_key_id,
        redis_cache_status="hit",
        semantic_cache_status=None,
        provider_called=False,
    )
    add_request(
        db,
        api_key_id,
        redis_cache_status="miss",
        semantic_cache_status="hit",
        provider_called=False,
    )
    add_request(
        db,
        api_key_id,
        redis_cache_status="miss",
        semantic_cache_status="miss",
        provider_called=True,
    )

    response = get_analytics(client, raw_api_key)

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 3,
        "redis_hits": 1,
        "redis_misses": 2,
        "semantic_hits": 1,
        "semantic_misses": 1,
        "provider_calls": 1,
        "cache_hits": 2,
        "cache_hit_rate": pytest.approx(200 / 3),
    }


def test_streaming_provider_request_with_null_cache_outcomes(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_request(
        db,
        api_key_id,
        redis_cache_status=None,
        semantic_cache_status=None,
        provider_called=None,
    )
    add_request(
        db,
        api_key_id,
        redis_cache_status=None,
        semantic_cache_status=None,
        provider_called=True,
    )

    response = get_analytics(client, raw_api_key)

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 2,
        "redis_hits": 0,
        "redis_misses": 0,
        "semantic_hits": 0,
        "semantic_misses": 0,
        "provider_calls": 1,
        "cache_hits": 0,
        "cache_hit_rate": 0.0,
    }


def test_cache_hit_rate_is_percentage_of_all_requests(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    for _ in range(3):
        add_request(
            db,
            api_key_id,
            redis_cache_status="hit",
            semantic_cache_status=None,
            provider_called=False,
        )
    for _ in range(2):
        add_request(
            db,
            api_key_id,
            redis_cache_status="miss",
            semantic_cache_status="miss",
            provider_called=True,
        )

    response = get_analytics(client, raw_api_key)

    assert response.status_code == 200
    assert response.json()["cache_hit_rate"] == 60.0


def test_cache_analytics_requires_api_key(analytics_client):
    client, _, _, _ = analytics_client

    response = client.get("/v1/analytics/cache")

    assert response.status_code == 401
