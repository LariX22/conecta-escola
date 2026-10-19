"""Configurações da aplicação, lidas de variáveis de ambiente (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Conecta Escola API"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+psycopg://conecta:conecta@localhost:5432/conecta_escola"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:19006"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
