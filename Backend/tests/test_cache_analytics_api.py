import hashlib
import os
import uuid
from datetime import datetime

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


def get_analytics(client, api_key, params=None):
    return client.get(
        "/v1/analytics/cache",
        headers={"Authorization": f"Bearer {api_key}"},
        params=params,
    )


def add_api_key(db, user_id, raw_key):
    api_key = APIKey(
        id=uuid.uuid4(),
        user_id=user_id,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    return api_key.id


def add_time_window_requests(db, api_key_id):
    rows = [
        (datetime(2026, 9, 30, 23, 59), "miss", "miss", True),
        (datetime(2026, 10, 1, 0, 0), "hit", None, False),
        (datetime(2026, 10, 1, 12, 0), "miss", "hit", False),
        (datetime(2026, 10, 2, 0, 0), "miss", "miss", True),
    ]
    for created_at, redis_status, semantic_status, provider_called in rows:
        add_request(
            db,
            api_key_id,
            created_at=created_at,
            redis_cache_status=redis_status,
            semantic_cache_status=semantic_status,
            provider_called=provider_called,
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
        "redis_errors": 0,
        "semantic_errors": 0,
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
        "redis_errors": 0,
        "semantic_errors": 0,
        "provider_calls": 1,
        "cache_hits": 2,
        "cache_hit_rate": pytest.approx(200 / 3),
    }


def test_cache_analytics_are_isolated_by_api_key_and_time_window(
    analytics_client,
):
    client, db, first_raw_key, first_key_id = analytics_client
    first_key = db.query(APIKey).filter(APIKey.id == first_key_id).one()
    second_raw_key = "analytics-second-test-key"
    second_key_id = add_api_key(db, first_key.user_id, second_raw_key)

    for created_at, redis_status, semantic_status, provider_called in [
        (datetime(2026, 10, 1, 8), "hit", None, False),
        (datetime(2026, 10, 1, 9), "miss", "hit", False),
        (datetime(2026, 10, 1, 10), "miss", "miss", True),
    ]:
        add_request(
            db,
            first_key_id,
            created_at=created_at,
            redis_cache_status=redis_status,
            semantic_cache_status=semantic_status,
            provider_called=provider_called,
        )
    add_request(
        db,
        second_key_id,
        created_at=datetime(2026, 10, 1, 11),
        redis_cache_status="miss",
        semantic_cache_status="miss",
        provider_called=True,
    )
    add_request(
        db,
        second_key_id,
        created_at=datetime(2026, 10, 3, 11),
        redis_cache_status="hit",
        semantic_cache_status=None,
        provider_called=False,
    )

    window = {
        "from": "2026-10-01T00:00:00Z",
        "to": "2026-10-02T00:00:00Z",
    }
    first_response = get_analytics(client, first_raw_key)
    second_response = get_analytics(client, second_raw_key)
    first_window_response = get_analytics(client, first_raw_key, params=window)
    second_window_response = get_analytics(
        client,
        second_raw_key,
        params=window,
    )

    assert first_response.status_code == second_response.status_code == 200
    assert first_response.json() == {
        "total_requests": 3,
        "redis_hits": 1,
        "redis_misses": 2,
        "semantic_hits": 1,
        "semantic_misses": 1,
        "redis_errors": 0,
        "semantic_errors": 0,
        "provider_calls": 1,
        "cache_hits": 2,
        "cache_hit_rate": pytest.approx(200 / 3),
    }
    assert second_response.json() == {
        "total_requests": 2,
        "redis_hits": 1,
        "redis_misses": 1,
        "semantic_hits": 0,
        "semantic_misses": 1,
        "redis_errors": 0,
        "semantic_errors": 0,
        "provider_calls": 1,
        "cache_hits": 1,
        "cache_hit_rate": 50.0,
    }
    assert first_window_response.json() == first_response.json()
    assert second_window_response.json() == {
        "total_requests": 1,
        "redis_hits": 0,
        "redis_misses": 1,
        "semantic_hits": 0,
        "semantic_misses": 1,
        "redis_errors": 0,
        "semantic_errors": 0,
        "provider_calls": 1,
        "cache_hits": 0,
        "cache_hit_rate": 0.0,
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
        "redis_errors": 0,
        "semantic_errors": 0,
        "provider_calls": 1,
        "cache_hits": 0,
        "cache_hit_rate": 0.0,
    }


def test_cache_lookup_errors_have_separate_analytics_counts(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_request(
        db,
        api_key_id,
        redis_cache_status="error",
        semantic_cache_status="error",
        provider_called=True,
    )

    response = get_analytics(client, raw_api_key)

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 1,
        "redis_hits": 0,
        "redis_misses": 0,
        "redis_errors": 1,
        "semantic_hits": 0,
        "semantic_misses": 0,
        "semantic_errors": 1,
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


def test_cache_analytics_from_only_is_inclusive(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_time_window_requests(db, api_key_id)

    response = get_analytics(
        client,
        raw_api_key,
        params={"from": "2026-10-01T00:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 3
    assert response.json()["redis_hits"] == 1


def test_cache_analytics_to_only_is_exclusive(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_time_window_requests(db, api_key_id)

    response = get_analytics(
        client,
        raw_api_key,
        params={"to": "2026-10-02T00:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 3
    assert response.json()["provider_calls"] == 1


def test_cache_analytics_from_and_to_filter_both_bounds(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_time_window_requests(db, api_key_id)

    response = get_analytics(
        client,
        raw_api_key,
        params={
            "from": "2026-10-01T00:00:00Z",
            "to": "2026-10-02T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 2
    assert response.json()["cache_hits"] == 2
    assert response.json()["cache_hit_rate"] == 100.0


def test_cache_analytics_empty_time_window_returns_zeroes(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_time_window_requests(db, api_key_id)

    response = get_analytics(
        client,
        raw_api_key,
        params={
            "from": "2026-10-03T00:00:00Z",
            "to": "2026-10-04T00:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 0
    assert response.json()["cache_hit_rate"] == 0.0


def test_cache_analytics_rejects_from_at_or_after_to(analytics_client):
    client, _, raw_api_key, _ = analytics_client

    response = get_analytics(
        client,
        raw_api_key,
        params={
            "from": "2026-10-02T00:00:00Z",
            "to": "2026-10-02T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "'from' must be earlier than 'to'"


def test_cache_analytics_normalizes_timezone_aware_timestamps(analytics_client):
    client, db, raw_api_key, api_key_id = analytics_client
    add_time_window_requests(db, api_key_id)

    response = get_analytics(
        client,
        raw_api_key,
        params={
            "from": "2026-10-01T02:00:00+02:00",
            "to": "2026-10-01T14:00:00+02:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 1
    assert response.json()["redis_hits"] == 1
