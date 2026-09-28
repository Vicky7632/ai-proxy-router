import os
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi import HTTPException

from app.db.models.api_key import APIKey
from app.db.models.provider import Provider
from app.db.models.request_log import RequestLog
from app.services import budget_service


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *criteria):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(self, api_key, provider=None, request_log=None):
        self.api_key = api_key
        self.provider = provider
        self.request_log = request_log
        self.committed = False
        self.closed = False

    def query(self, model):
        if model is APIKey:
            return FakeQuery(self.api_key)
        if model is Provider:
            return FakeQuery(self.provider)
        if model is RequestLog:
            return FakeQuery(self.request_log)
        raise AssertionError(f"Unexpected model: {model}")

    def commit(self):
        self.committed = True

    def rollback(self):
        return None

    def close(self):
        self.closed = True


def test_calculate_cost_uses_provider_pricing():
    provider = SimpleNamespace(
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.01,
    )

    assert budget_service.calculate_cost(provider, 1000, 1000) == 0.02


def test_update_spend_updates_api_key_and_matching_request_log(monkeypatch):
    api_key_id = uuid4()
    request_log_id = uuid4()
    api_key = SimpleNamespace(
        id=api_key_id,
        budget_limit=0.02,
        current_spend=0.0,
        budget_reset_at=datetime(2027, 1, 1),
    )
    request_log = SimpleNamespace(id=request_log_id, cost=0.0)
    provider = SimpleNamespace(
        name="provider-name",
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.01,
    )
    db = FakeSession(api_key, provider, request_log)
    monkeypatch.setattr(budget_service, "SessionLocal", lambda: db)

    cost = budget_service.update_spend(
        api_key_id,
        "provider-name",
        1000,
        1000,
        request_log_id=request_log_id,
    )

    assert cost == 0.02
    assert api_key.current_spend == 0.02
    assert request_log.cost == 0.02
    assert db.committed
    assert db.closed


@pytest.mark.asyncio
async def test_budget_guard_blocks_at_zero_remaining(monkeypatch):
    api_key_id = uuid4()
    api_key = SimpleNamespace(
        id=api_key_id,
        budget_limit=0.02,
        current_spend=0.02,
        budget_reset_at=datetime(2027, 1, 1),
    )
    db = FakeSession(api_key)
    monkeypatch.setattr(budget_service, "SessionLocal", lambda: db)

    with pytest.raises(HTTPException) as error:
        await budget_service.check_budget(api_key)

    assert error.value.status_code == 403
    assert error.value.detail == "Monthly budget exceeded."


@pytest.mark.asyncio
async def test_expired_budget_resets_and_advances_by_month(monkeypatch):
    api_key_id = uuid4()
    api_key = SimpleNamespace(
        id=api_key_id,
        budget_limit=0.02,
        current_spend=0.02,
        budget_reset_at=datetime(2026, 8, 31, 10, 30),
    )
    db = FakeSession(api_key)
    monkeypatch.setattr(budget_service, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        budget_service,
        "_utcnow",
        lambda: datetime(2026, 9, 28, 12),
    )

    remaining = await budget_service.check_budget(api_key)

    assert remaining == 0.02
    assert api_key.current_spend == 0
    assert api_key.budget_reset_at == datetime(2026, 9, 30, 10, 30)
    assert db.committed
