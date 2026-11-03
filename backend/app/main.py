"""Ponto de entrada da aplicação FastAPI."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_classrooms import router as classrooms_router
from app.api.routes_health import router as health_router
from app.api.routes_schools import router as schools_router
from app.api.routes_students import router as students_router
from app.core.config import get_settings
from app.db import base  # noqa: F401  (garante que todos os modelos sejam registrados no metadata)

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(schools_router, prefix="/api/v1")
app.include_router(students_router, prefix="/api/v1")
app.include_router(classrooms_router, prefix="/api/v1")
