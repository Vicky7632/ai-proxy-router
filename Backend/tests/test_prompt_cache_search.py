import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.db.models.prompt_cache import PromptCache
from app.db.repositories import prompt_cache_repository
from app.db.repositories.prompt_cache_repository import PromptCacheCandidate
from app.services import prompt_cache_service


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = ()
        self.ordering = ()
        self.row_limit = None
        self.first_called = False

    def filter(self, *criteria):
        self.filters += criteria
        return self

    def order_by(self, *ordering):
        self.ordering = ordering
        return self

    def limit(self, count):
        self.row_limit = count
        return self

    def first(self):
        self.first_called = True
        now = datetime.now(timezone.utc)
        valid_rows = [
            row
            for row in self.rows
            if row[0].expires_at is None or row[0].expires_at > now
        ]
        valid_rows.sort(key=lambda row: row[1])
        return valid_rows[0] if valid_rows else None


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.query_arguments = None
        self.query_instance = None
        self.rolled_back = False
        self.closed = False

    def query(self, *entities):
        self.query_arguments = entities
        self.query_instance = FakeQuery(self.rows)
        return self.query_instance

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def cache_entry(
    entry_id,
    prompt,
    *,
    expires_at=None,
    response=None,
    model="test-model",
    provider="test-provider",
):
    return SimpleNamespace(
        id=entry_id,
        prompt=prompt,
        response=response or {"prompt": prompt},
        model=model,
        provider=provider,
        expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_repository_uses_cosine_distance_and_returns_nearest_valid_entry(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    expired = cache_entry(
        1,
        "expired",
        expires_at=now - timedelta(seconds=1),
    )
    farther = cache_entry(2, "farther", expires_at=now + timedelta(hours=1))
    nearest = cache_entry(3, "nearest")
    db = FakeSession([(nearest, 0.08), (expired, 0.01), (farther, 0.2)])
    monkeypatch.setattr(prompt_cache_repository, "SessionLocal", lambda: db)

    result = prompt_cache_repository.find_nearest_prompt_cache(
        [0.0] * 768,
        model="test-model",
    )

    assert result == PromptCacheCandidate(
        id=3,
        prompt="nearest",
        response={"prompt": "nearest"},
        model="test-model",
        provider="test-provider",
        cosine_distance=0.08,
    )
    distance_expression = db.query_arguments[1]
    assert "<=>" in str(
        distance_expression.compile(dialect=postgresql.dialect())
    )
    filter_sql = " ".join(
        str(condition.compile(dialect=postgresql.dialect()))
        for condition in db.query_instance.filters
    )
    assert "expires_at IS NULL" in filter_sql
    assert "expires_at > now()" in filter_sql
    assert "IS NOT NULL" in filter_sql
    assert "prompt_cache.model =" in filter_sql
    assert db.query_instance.row_limit == 1
    assert db.query_instance.first_called
    assert db.closed


@pytest.mark.asyncio
async def test_repository_keeps_non_expiring_entry_eligible(monkeypatch):
    entry = cache_entry(4, "never expires")
    db = FakeSession([(entry, 0.0)])
    monkeypatch.setattr(prompt_cache_repository, "SessionLocal", lambda: db)

    result = prompt_cache_repository.find_nearest_prompt_cache([0.0] * 768)

    assert result is not None
    assert result.id == 4
    assert result.cosine_distance == 0.0


@pytest.mark.asyncio
async def test_service_returns_hit_and_correct_similarity(monkeypatch):
    candidate = PromptCacheCandidate(
        id=5,
        prompt="similar prompt",
        response={"answer": "cached"},
        model="test-model",
        provider="gemini",
        cosine_distance=0.08,
    )
    monkeypatch.setattr(
        prompt_cache_service,
        "find_nearest_prompt_cache",
        lambda embedding: candidate,
    )

    result = await prompt_cache_service.find_similar_prompt_cache(
        [0.0] * 768,
        similarity_threshold=0.9,
    )

    assert result is not None
    assert result.id == 5
    assert result.prompt == "similar prompt"
    assert result.similarity == pytest.approx(0.92)
    assert result.response == {"answer": "cached"}
    assert result.model == "test-model"
    assert result.provider == "gemini"


@pytest.mark.asyncio
async def test_service_returns_miss_below_similarity_threshold(monkeypatch):
    monkeypatch.setattr(
        prompt_cache_service,
        "find_nearest_prompt_cache",
        lambda embedding: PromptCacheCandidate(
            id=6,
            prompt="different prompt",
            response={},
            model="test-model",
            provider=None,
            cosine_distance=0.21,
        ),
    )

    result = await prompt_cache_service.find_similar_prompt_cache(
        [0.0] * 768,
        similarity_threshold=0.8,
    )

    assert result is None


@pytest.mark.asyncio
async def test_service_accepts_similarity_equal_to_threshold(monkeypatch):
    monkeypatch.setattr(
        prompt_cache_service,
        "find_nearest_prompt_cache",
        lambda embedding: PromptCacheCandidate(
            id=7,
            prompt="boundary prompt",
            response={},
            model="test-model",
            provider=None,
            cosine_distance=0.1,
        ),
    )

    result = await prompt_cache_service.find_similar_prompt_cache(
        [0.0] * 768,
        similarity_threshold=0.9,
    )

    assert result is not None
    assert result.similarity == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_service_uses_configured_threshold_by_default(monkeypatch):
    monkeypatch.setattr(settings, "semantic_cache_similarity_threshold", 0.95)
    monkeypatch.setattr(
        prompt_cache_service,
        "find_nearest_prompt_cache",
        lambda embedding: PromptCacheCandidate(
            id=8,
            prompt="prompt",
            response={},
            model="test-model",
            provider=None,
            cosine_distance=0.08,
        ),
    )

    result = await prompt_cache_service.find_similar_prompt_cache([0.0] * 768)

    assert result is None


@pytest.mark.asyncio
async def test_service_rejects_invalid_embedding_dimension(monkeypatch):
    called = False

    def unexpected_search(embedding):
        nonlocal called
        called = True
        raise AssertionError("Invalid embedding must be rejected before query")

    monkeypatch.setattr(
        prompt_cache_service,
        "find_nearest_prompt_cache",
        unexpected_search,
    )

    with pytest.raises(ValueError, match="exactly 768 dimensions"):
        await prompt_cache_service.find_similar_prompt_cache([0.0] * 767)

    assert not called


def test_prompt_cache_model_has_768_dimensional_vector():
    assert PromptCache.__table__.c.embedding.type.dim == 768
