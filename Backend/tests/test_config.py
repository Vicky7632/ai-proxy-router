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


def test_provider_health_settings_have_defaults(monkeypatch):
    monkeypatch.delenv("PROVIDER_HEALTH_FAILURE_THRESHOLD", raising=False)
    monkeypatch.delenv("PROVIDER_HEALTH_COOLDOWN_SECONDS", raising=False)

    configured = make_settings()

    assert configured.provider_health_failure_threshold == 3
    assert configured.provider_health_cooldown_seconds == 60


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("provider_health_failure_threshold", 0),
        ("provider_health_failure_threshold", -1),
        ("provider_health_failure_threshold", True),
        ("provider_health_cooldown_seconds", 0),
        ("provider_health_cooldown_seconds", -1),
        ("provider_health_cooldown_seconds", True),
    ],
)
def test_provider_health_settings_must_be_positive_integers(setting, value):
    with pytest.raises(ValidationError):
        make_settings(**{setting: value})
