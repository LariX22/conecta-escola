"""Configurações da aplicação, lidas de variáveis de ambiente (.env)."""
from functools import lru_cache

from pydantic import field_validator
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

    # Primeiro administrador técnico, criado na inicialização se ainda não existir.
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "Administrador Técnico"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Provedores como o Render entregam "postgres://" ou "postgresql://", que o
        # SQLAlchemy abriria com psycopg2 (não instalado). Forçamos o driver psycopg 3.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
