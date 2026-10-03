from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    groq_api_key: str
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    semantic_cache_similarity_threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
    )
    semantic_cache_ttl_seconds: int = Field(default=3600, gt=0)
    semantic_cache_cleanup_interval_seconds: int = Field(default=3600, gt=0)
    redis_url: str | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str = "default"
    redis_password: str | None = None
    redis_ssl: bool = False
    redis_db: int = 0
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    frontend_origin: str = "http://localhost:3000"

    @field_validator("semantic_cache_cleanup_interval_seconds", mode="before")
    @classmethod
    def validate_semantic_cache_cleanup_interval(cls, value):
        if isinstance(value, bool):
            raise ValueError("Semantic cache cleanup interval must be a positive integer")
        return value

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

settings = Settings()