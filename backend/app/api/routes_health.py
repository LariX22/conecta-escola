"""Rota simples de verificação de saúde da API (usada por Docker healthcheck)."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
