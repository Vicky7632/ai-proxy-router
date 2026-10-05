import hashlib
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.api_key import APIKey
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services.provider_health_service import ProviderHealth


@compiles(UUID, "sqlite")
def compile_postgresql_uuid_for_sqlite(type_, compiler, **kwargs):
    return "CHAR(32)"


class FakeProviderHealthService:
    def __init__(self, health):
        self.health = health

    async def get_all_health(self):
        return self.health


@pytest.fixture
def provider_health_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, APIKey.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    user = User(
        id=uuid.uuid4(),
        email="provider-health@example.test",
        hashed_password="not-used",
    )
    raw_api_key = "provider-health-test-key"
    db.add(user)
    db.add(
        APIKey(
            id=uuid.uuid4(),
            user_id=user.id,
            key_hash=hashlib.sha256(raw_api_key.encode()).hexdigest(),
            is_active=True,
        )
    )
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
            yield client, raw_api_key
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_provider_health_returns_all_configured_provider_states(
    provider_health_client, monkeypatch
):
    from app.api.v1 import providers

    success_at = datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)
    failure_at = datetime(2026, 10, 5, 4, 5, tzinfo=timezone.utc)
    health = {
        "groq": ProviderHealth(
            total_requests=12,
            total_failures=2,
            consecutive_failures=1,
            last_success_at=success_at,
            last_failure_at=failure_at,
        ),
        "gemini": ProviderHealth(
            total_requests=4,
            total_failures=4,
            consecutive_failures=4,
            last_failure_at=failure_at,
        ),
        "openrouter": ProviderHealth(
            total_requests=8,
            total_failures=0,
            consecutive_failures=0,
            last_success_at=success_at,
        ),
        "unexpected-provider": ProviderHealth(total_requests=99),
    }
    monkeypatch.setattr(
        providers,
        "provider_health_service",
        FakeProviderHealthService(health),
    )
    client, raw_api_key = provider_health_client

    response = client.get(
        "/v1/providers/health",
        headers={"Authorization": f"Bearer {raw_api_key}"},
    )

    assert response.status_code == 200
    response_providers = response.json()["providers"]
    assert set(response_providers) == {"groq", "gemini", "openrouter"}
    assert response_providers["groq"] == {
        "total_requests": 12,
        "total_failures": 2,
        "consecutive_failures": 1,
        "last_success_at": "2026-10-05T04:00:00Z",
        "last_failure_at": "2026-10-05T04:05:00Z",
    }
    assert response_providers["gemini"]["total_requests"] == 4
    assert response_providers["openrouter"]["total_failures"] == 0
    assert set(response_providers["groq"]) == {
        "total_requests",
        "total_failures",
        "consecutive_failures",
        "last_success_at",
        "last_failure_at",
    }
    assert "unexpected-provider" not in response.text
    assert raw_api_key not in response.text


def test_provider_health_uses_empty_defaults_for_unrecorded_providers(
    provider_health_client, monkeypatch
):
    from app.api.v1 import providers

    monkeypatch.setattr(
        providers,
        "provider_health_service",
        FakeProviderHealthService({}),
    )
    client, raw_api_key = provider_health_client

    response = client.get(
        "/v1/providers/health",
        headers={"Authorization": f"Bearer {raw_api_key}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "providers": {
            provider: {
                "total_requests": 0,
                "total_failures": 0,
                "consecutive_failures": 0,
                "last_success_at": None,
                "last_failure_at": None,
            }
            for provider in ("groq", "gemini", "openrouter")
        }
    }


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-key"])
def test_provider_health_rejects_missing_or_invalid_api_key(
    provider_health_client, authorization
):
    client, _ = provider_health_client
    headers = (
        {"Authorization": authorization}
        if authorization is not None
        else {}
    )

    response = client.get("/v1/providers/health", headers=headers)

    assert response.status_code == 401
