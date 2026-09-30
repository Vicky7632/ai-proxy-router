import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from pgvector.sqlalchemy import Vector

from app.db.models.prompt_cache import PromptCache
from app.db.repositories import prompt_cache_repository
from app.services import prompt_cache_service


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def add(self, instance):
        self.added.append(instance)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_save_prompt_cache_persists_entry(monkeypatch):
    db = FakeSession()
    monkeypatch.setattr(prompt_cache_repository, "SessionLocal", lambda: db)
    embedding = [index / 768 for index in range(768)]
    expires_at = datetime(2027, 1, 1, tzinfo=timezone.utc)
    response = {"choices": [{"message": {"content": "hello"}}]}

    await prompt_cache_service.save_prompt_cache(
        prompt="hello",
        embedding=embedding,
        response=response,
        model="gemini-embedding-2-preview",
        provider="gemini",
        expires_at=expires_at,
    )

    assert len(db.added) == 1
    entry = db.added[0]
    assert isinstance(entry, PromptCache)
    assert entry.prompt == "hello"
    assert entry.embedding == embedding
    assert entry.response == response
    assert entry.model == "gemini-embedding-2-preview"
    assert entry.provider == "gemini"
    assert entry.expires_at == expires_at
    assert PromptCache.__table__.c.embedding.type.dim == 768
    assert db.committed
    assert not db.rolled_back
    assert db.closed


@pytest.mark.asyncio
async def test_save_prompt_cache_supports_optional_provider_and_expiry(monkeypatch):
    db = FakeSession()
    monkeypatch.setattr(prompt_cache_repository, "SessionLocal", lambda: db)

    await prompt_cache_service.save_prompt_cache(
        prompt="hello",
        embedding=[0.0] * 768,
        response={"cached": True},
        model="test-model",
    )

    entry = db.added[0]
    assert entry.provider is None
    assert entry.expires_at is None
    assert db.committed


@pytest.mark.asyncio
async def test_save_prompt_cache_rejects_invalid_embedding_dimension(monkeypatch):
    session_created = False

    def unexpected_session():
        nonlocal session_created
        session_created = True
        raise AssertionError("Invalid embedding must be rejected before DB use")

    monkeypatch.setattr(
        prompt_cache_repository,
        "SessionLocal",
        unexpected_session,
    )

    with pytest.raises(ValueError, match="exactly 768 dimensions"):
        await prompt_cache_service.save_prompt_cache(
            prompt="hello",
            embedding=[0.0] * 767,
            response={},
            model="test-model",
        )

    assert not session_created


def test_prompt_cache_embedding_column_uses_pgvector_768():
    embedding_type = PromptCache.__table__.c.embedding.type

    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == 768
