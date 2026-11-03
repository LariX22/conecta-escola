"""Modelos de Aluno (Student) e vínculo entre aluno e responsável.

Um aluno pode ter vários responsáveis autorizados, e um responsável
(usuário com papel `responsavel`) pode estar vinculado a vários alunos,
inclusive de turmas diferentes — refletido em `StudentGuardianLink`.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import GUID


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentGuardianLink(Base):
    __tablename__ = "student_guardian_links"
    __table_args__ = (UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    guardian_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_label: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["Student"] = relationship("Student")
