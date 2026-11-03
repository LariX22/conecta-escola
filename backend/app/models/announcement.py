"""Modelos de Comunicado e confirmação de leitura.

Um comunicado é publicado por alguém da escola para a escola inteira
(`audience="school"`) ou para turmas específicas (`audience="classrooms"`).

Os destinatários são os responsáveis: todos da escola, ou os dos alunos
com matrícula ativa nas turmas alvo. Eles são calculados no momento da
consulta (não há cópia da lista), então um responsável vinculado depois
também passa a ver comunicados já publicados para a turma do filho.

`AnnouncementRead` registra quando cada responsável confirmou a leitura.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import GUID

AUDIENCE_SCHOOL = "school"
AUDIENCE_CLASSROOMS = "classrooms"


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint("audience IN ('school', 'classrooms')", name="ck_announcements_audience"),
        Index("ix_announcements_school_publish_at", "school_id", "publish_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship("User", lazy="joined")
    targets: Mapped[list["AnnouncementClassroom"]] = relationship(
        "AnnouncementClassroom", cascade="all, delete-orphan", lazy="selectin"
    )
    reads: Mapped[list["AnnouncementRead"]] = relationship("AnnouncementRead", cascade="all, delete-orphan")


class AnnouncementClassroom(Base):
    """Turma alvo de um comunicado com `audience="classrooms"`."""

    __tablename__ = "announcement_classrooms"
    __table_args__ = (UniqueConstraint("announcement_id", "classroom_id", name="uq_announcement_classroom"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AnnouncementRead(Base):
    """Confirmação de leitura de um responsável (no máximo uma por comunicado)."""

    __tablename__ = "announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read_user"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
