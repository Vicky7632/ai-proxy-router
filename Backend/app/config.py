from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    groq_api_key: str
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
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

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

settings = Settings()