"""cadastros: students, classrooms, enrollments, teacher_classroom_assignments, student_guardian_links

Revision ID: 0002_cadastros
Revises: 0001_initial
Create Date: 2026-10-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_cadastros"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_students_school_id", "students", ["school_id"])

    op.create_table(
        "classrooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("segment", sa.String(length=100), nullable=False),
        sa.Column("school_year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("school_id", "name", "school_year", name="uq_classroom_school_name_year"),
    )
    op.create_index("ix_classrooms_school_id", "classrooms", ["school_id"])

    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "classroom_id", name="uq_enrollment_student_classroom"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_classroom_id", "enrollments", ["classroom_id"])

    op.create_table(
        "teacher_classroom_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("teacher_id", "classroom_id", name="uq_teacher_classroom"),
    )
    op.create_index("ix_teacher_classroom_assignments_teacher_id", "teacher_classroom_assignments", ["teacher_id"])
    op.create_index("ix_teacher_classroom_assignments_classroom_id", "teacher_classroom_assignments", ["classroom_id"])

    op.create_table(
        "student_guardian_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_label", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),
    )
    op.create_index("ix_student_guardian_links_student_id", "student_guardian_links", ["student_id"])
    op.create_index("ix_student_guardian_links_guardian_id", "student_guardian_links", ["guardian_id"])


def downgrade() -> None:
    op.drop_index("ix_student_guardian_links_guardian_id", table_name="student_guardian_links")
    op.drop_index("ix_student_guardian_links_student_id", table_name="student_guardian_links")
    op.drop_table("student_guardian_links")

    op.drop_index("ix_teacher_classroom_assignments_classroom_id", table_name="teacher_classroom_assignments")
    op.drop_index("ix_teacher_classroom_assignments_teacher_id", table_name="teacher_classroom_assignments")
    op.drop_table("teacher_classroom_assignments")

    op.drop_index("ix_enrollments_classroom_id", table_name="enrollments")
    op.drop_index("ix_enrollments_student_id", table_name="enrollments")
    op.drop_table("enrollments")

    op.drop_index("ix_classrooms_school_id", table_name="classrooms")
    op.drop_table("classrooms")

    op.drop_index("ix_students_school_id", table_name="students")
    op.drop_table("students")
