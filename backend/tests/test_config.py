"""Testes da normalização da URL do banco de dados."""
import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgres://usuario:senha@dpg-abc/conecta",
        "postgresql://usuario:senha@dpg-abc/conecta",
        "postgresql+psycopg://usuario:senha@dpg-abc/conecta",
    ],
)
def test_database_url_always_uses_psycopg_driver(raw_url):
    settings = Settings(database_url=raw_url)
    assert settings.database_url == "postgresql+psycopg://usuario:senha@dpg-abc/conecta"


def test_database_url_keeps_other_schemes_untouched():
    settings = Settings(database_url="sqlite:///:memory:")
    assert settings.database_url == "sqlite:///:memory:"
