"""Utilitários de data/hora: sempre UTC com fuso, para comparar e gravar de forma consistente."""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normaliza para UTC. Valores sem fuso (ex.: lidos do SQLite nos testes) são tratados como UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
