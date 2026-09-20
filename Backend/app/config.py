from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    groq_api_key: str
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()