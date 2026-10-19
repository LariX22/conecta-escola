"""Modelos de Usuário e Papel (Role).

Papéis previstos inicialmente: direcao, secretaria, professor,
coordenacao_pedagogica, responsavel, aluno, admin_tecnico.

O `admin_tecnico` não possui `school_id` (atua sobre a infraestrutura,
não sobre o conteúdo pedagógico de uma escola específica).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import GUID


class RoleName(str, enum.Enum):
    DIRECAO = "direcao"
    SECRETARIA = "secretaria"
    PROFESSOR = "professor"
    COORDENACAO_PEDAGOGICA = "coordenacao_pedagogica"
    RESPONSAVEL = "responsavel"
    ALUNO = "aluno"
    ADMIN_TECNICO = "admin_tecnico"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        unique=True,
        nullable=False,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("roles.id"), nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship("Role")
