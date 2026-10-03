import asyncio
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

import app.main as main
from app.db.repositories import prompt_cache_repository
from app.services import semantic_cache_cleanup_service


class FakeQuery:
    def __init__(self, session):
        self.session = session
        self.criteria = ()

    def filter(self, *criteria):
        self.criteria = criteria
        return self

    def delete(self, synchronize_session):
        assert synchronize_session is False
        cutoff = self.criteria[1].right.value
        expired = [
            row
            for row in self.session.rows
            if row.expires_at is not None and row.expires_at <= cutoff
        ]
        for row in expired:
            self.session.rows.remove(row)
        return len(expired)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.query_instance = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def query(self, model):
        self.query_instance = FakeQuery(self)
        return self.query_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_cleanup_deletes_expired_rows_and_returns_count(monkeypatch):
    now = datetime.now(timezone.utc)
    expired = SimpleNamespace(expires_at=now - timedelta(seconds=1))
    non_expired = SimpleNamespace(expires_at=now + timedelta(hours=1))
    non_expiring = SimpleNamespace(expires_at=None)
    db = FakeSession([expired, non_expired, non_expiring])
    monkeypatch.setattr(prompt_cache_repository, "SessionLocal", lambda: db)

    deleted_count = prompt_cache_repository.delete_expired_prompt_cache()

    assert deleted_count == 1
    assert db.rows == [non_expired, non_expiring]
    assert db.committed
    assert not db.rolled_back
    assert db.closed
    filter_sql = " ".join(
        str(condition.compile(dialect=postgresql.dialect()))
        for condition in db.query_instance.criteria
    )
    assert "expires_at IS NOT NULL" in filter_sql
    assert "expires_at <=" in filter_sql


@pytest.mark.asyncio
async def test_cleanup_service_returns_repository_deleted_count(monkeypatch):
    def delete_expired():
        return 3

    monkeypatch.setattr(
        semantic_cache_cleanup_service,
        "delete_expired_prompt_cache",
        delete_expired,
    )

    assert await semantic_cache_cleanup_service.cleanup_expired_prompt_cache() == 3


@pytest.mark.asyncio
async def test_cleanup_failure_is_logged_and_loop_continues(caplog, monkeypatch):
    stop_event = asyncio.Event()
    call_count = 0

    async def cleanup():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("database unavailable")
        stop_event.set()
        return 0

    monkeypatch.setattr(
        semantic_cache_cleanup_service,
        "cleanup_expired_prompt_cache",
        cleanup,
    )
    with caplog.at_level(logging.ERROR):
        await semantic_cache_cleanup_service.run_semantic_cache_cleanup_loop(
            stop_event,
            interval_seconds=0.001,
        )

    assert call_count == 2
    assert "Semantic cache cleanup failed" in caplog.text
    assert "database unavailable" in caplog.text


@pytest.mark.asyncio
async def test_lifespan_stops_cleanup_task_cleanly(monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def cleanup_loop(stop_event, interval_seconds):
        started.set()
        try:
            await stop_event.wait()
        finally:
            stopped.set()

    monkeypatch.setattr(main, "run_semantic_cache_cleanup_loop", cleanup_loop)

    async with main.app.router.lifespan_context(main.app):
        await asyncio.wait_for(started.wait(), timeout=1)

    assert stopped.is_set()
