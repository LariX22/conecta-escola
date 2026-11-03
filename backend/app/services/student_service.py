"""Regras de negócio para alunos e vínculos com responsáveis.

Todas as consultas aqui filtram explicitamente por `school_id` para
garantir o isolamento multi-tenant também no nível de serviço (nunca
apenas confiando em filtros feitos pela interface).
"""
import uuid

from sqlalchemy.orm import Session

from app.models.student import Student, StudentGuardianLink
from app.models.user import RoleName, User
from app.schemas.student import StudentCreateRequest, StudentUpdateRequest


class StudentNotFoundError(Exception):
    pass


class GuardianNotFoundError(Exception):
    pass


class GuardianAlreadyLinkedError(Exception):
    pass


def create_student(db: Session, school_id: uuid.UUID, data: StudentCreateRequest) -> Student:
    student = Student(school_id=school_id, full_name=data.full_name, birth_date=data.birth_date)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def list_students_for_school(db: Session, school_id: uuid.UUID) -> list[Student]:
    return db.query(Student).filter(Student.school_id == school_id).order_by(Student.full_name).all()


def list_students_for_guardian(db: Session, guardian_id: uuid.UUID) -> list[Student]:
    return (
        db.query(Student)
        .join(StudentGuardianLink, StudentGuardianLink.student_id == Student.id)
        .filter(StudentGuardianLink.guardian_id == guardian_id)
        .order_by(Student.full_name)
        .all()
    )


def get_student_in_school(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    student = db.query(Student).filter(Student.id == student_id, Student.school_id == school_id).first()
    if student is None:
        raise StudentNotFoundError(f"Aluno não encontrado: {student_id}")
    return student


def guardian_has_access_to_student(db: Session, guardian_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    return (
        db.query(StudentGuardianLink)
        .filter(StudentGuardianLink.guardian_id == guardian_id, StudentGuardianLink.student_id == student_id)
        .first()
        is not None
    )


def update_student(db: Session, school_id: uuid.UUID, student_id: uuid.UUID, data: StudentUpdateRequest) -> Student:
    student = get_student_in_school(db, school_id, student_id)
    if data.full_name is not None:
        student.full_name = data.full_name
    if data.birth_date is not None:
        student.birth_date = data.birth_date
    if data.is_active is not None:
        student.is_active = data.is_active
    db.commit()
    db.refresh(student)
    return student


def link_guardian(
    db: Session, school_id: uuid.UUID, student_id: uuid.UUID, guardian_id: uuid.UUID, relationship_label: str
) -> StudentGuardianLink:
    get_student_in_school(db, school_id, student_id)  # garante que o aluno é da mesma escola

    guardian = (
        db.query(User)
        .filter(User.id == guardian_id, User.school_id == school_id, User.role.has(name=RoleName.RESPONSAVEL))
        .first()
    )
    if guardian is None:
        raise GuardianNotFoundError(f"Responsável não encontrado nesta escola: {guardian_id}")

    existing = (
        db.query(StudentGuardianLink)
        .filter(StudentGuardianLink.student_id == student_id, StudentGuardianLink.guardian_id == guardian_id)
        .first()
    )
    if existing is not None:
        raise GuardianAlreadyLinkedError("Este responsável já está vinculado a este aluno.")

    link = StudentGuardianLink(student_id=student_id, guardian_id=guardian_id, relationship_label=relationship_label)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
