import pytest
from pydantic import ValidationError

from app.config import Settings


def make_settings(**values):
    return Settings(
        database_url="sqlite:///./test.db",
        groq_api_key="test-groq-key",
        jwt_secret_key="test-secret",
        _env_file=None,
        **values,
    )


def test_semantic_cache_ttl_defaults_to_one_hour(monkeypatch):
    monkeypatch.delenv("SEMANTIC_CACHE_TTL_SECONDS", raising=False)

    assert make_settings().semantic_cache_ttl_seconds == 3600


def test_semantic_cache_ttl_reads_custom_environment_value(monkeypatch):
    monkeypatch.setenv("SEMANTIC_CACHE_TTL_SECONDS", "180")

    assert make_settings().semantic_cache_ttl_seconds == 180


@pytest.mark.parametrize("ttl", [0, -1])
def test_semantic_cache_ttl_must_be_positive(ttl):
    with pytest.raises(ValidationError):
        make_settings(semantic_cache_ttl_seconds=ttl)


def test_semantic_cache_cleanup_interval_defaults_to_one_hour(monkeypatch):
    monkeypatch.delenv("SEMANTIC_CACHE_CLEANUP_INTERVAL_SECONDS", raising=False)

    assert make_settings().semantic_cache_cleanup_interval_seconds == 3600


def test_semantic_cache_cleanup_interval_reads_custom_environment_value(
    monkeypatch,
):
    monkeypatch.setenv("SEMANTIC_CACHE_CLEANUP_INTERVAL_SECONDS", "180")

    assert make_settings().semantic_cache_cleanup_interval_seconds == 180


@pytest.mark.parametrize("interval", [0, -1, True])
def test_semantic_cache_cleanup_interval_must_be_positive_integer(interval):
    with pytest.raises(ValidationError):
        make_settings(semantic_cache_cleanup_interval_seconds=interval)
