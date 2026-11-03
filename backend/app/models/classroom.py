"""Modelos de Turma (Classroom) e Matrícula (Enrollment).

`Classroom` representa uma turma de uma escola em um determinado ano
letivo. `Enrollment` vincula um aluno a uma turma em um ano letivo
específico, permitindo histórico de matrículas ao longo dos anos.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import GUID


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("school_id", "name", "school_year", name="uq_classroom_school_name_year"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    segment: Mapped[str] = mapped_column(String(100), nullable=False)
    school_year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "classroom_id", name="uq_enrollment_student_classroom"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    classroom_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["Student"] = relationship("Student")
    classroom: Mapped["Classroom"] = relationship("Classroom")


class TeacherClassroomAssignment(Base):
    __tablename__ = "teacher_classroom_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "classroom_id", name="uq_teacher_classroom"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    classroom_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
