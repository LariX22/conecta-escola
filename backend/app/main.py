"""Ponto de entrada da aplicação FastAPI."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes_auth import router as auth_router
from app.api.routes_classrooms import router as classrooms_router
from app.api.routes_health import router as health_router
from app.api.routes_schools import router as schools_router
from app.api.routes_students import router as students_router
from app.api.routes_users import router as users_router
from app.core.config import get_settings
from app.db import base  # noqa: F401  (garante que todos os modelos sejam registrados no metadata)
from app.db.session import SessionLocal
from app.services.bootstrap_service import ensure_bootstrap_admin

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        try:
            with SessionLocal() as db:
                ensure_bootstrap_admin(
                    db,
                    settings.bootstrap_admin_email,
                    settings.bootstrap_admin_password,
                    settings.bootstrap_admin_name,
                )
        except SQLAlchemyError:
            logger.exception("Não foi possível criar o administrador inicial (as migrações foram aplicadas?).")
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(schools_router, prefix="/api/v1")
app.include_router(students_router, prefix="/api/v1")
app.include_router(classrooms_router, prefix="/api/v1")
