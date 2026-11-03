"""Regras de negócio para turmas, matrículas e atribuições de professores.

Reforça as regras de integridade que não são garantidas só pelas
chaves estrangeiras: aluno/turma/professor devem pertencer à mesma
escola para que um vínculo seja criado.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.classroom import Classroom, Enrollment, TeacherClassroomAssignment
from app.models.student import Student
from app.models.user import RoleName, User
from app.schemas.classroom import ClassroomCreateRequest


class ClassroomNotFoundError(Exception):
    pass


class ClassroomAlreadyExistsError(Exception):
    pass


class StudentNotInSchoolError(Exception):
    pass


class TeacherNotInSchoolError(Exception):
    pass


class AlreadyEnrolledError(Exception):
    pass


class AlreadyAssignedError(Exception):
    pass


def create_classroom(db: Session, school_id: uuid.UUID, data: ClassroomCreateRequest) -> Classroom:
    existing = (
        db.query(Classroom)
        .filter(Classroom.school_id == school_id, Classroom.name == data.name, Classroom.school_year == data.school_year)
        .first()
    )
    if existing is not None:
        raise ClassroomAlreadyExistsError("Já existe uma turma com este nome neste ano letivo.")

    classroom = Classroom(school_id=school_id, name=data.name, segment=data.segment, school_year=data.school_year)
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


def list_classrooms_for_school(db: Session, school_id: uuid.UUID) -> list[Classroom]:
    return db.query(Classroom).filter(Classroom.school_id == school_id).order_by(Classroom.school_year.desc(), Classroom.name).all()


def list_classrooms_for_teacher(db: Session, teacher_id: uuid.UUID) -> list[Classroom]:
    return (
        db.query(Classroom)
        .join(TeacherClassroomAssignment, TeacherClassroomAssignment.classroom_id == Classroom.id)
        .filter(TeacherClassroomAssignment.teacher_id == teacher_id)
        .order_by(Classroom.school_year.desc(), Classroom.name)
        .all()
    )


def get_classroom_in_school(db: Session, school_id: uuid.UUID, classroom_id: uuid.UUID) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id, Classroom.school_id == school_id).first()
    if classroom is None:
        raise ClassroomNotFoundError(f"Turma não encontrada: {classroom_id}")
    return classroom


def teacher_has_access_to_classroom(db: Session, teacher_id: uuid.UUID, classroom_id: uuid.UUID) -> bool:
    return (
        db.query(TeacherClassroomAssignment)
        .filter(TeacherClassroomAssignment.teacher_id == teacher_id, TeacherClassroomAssignment.classroom_id == classroom_id)
        .first()
        is not None
    )


def enroll_student(db: Session, school_id: uuid.UUID, classroom_id: uuid.UUID, student_id: uuid.UUID) -> Enrollment:
    classroom = get_classroom_in_school(db, school_id, classroom_id)

    student = db.query(Student).filter(Student.id == student_id, Student.school_id == school_id).first()
    if student is None:
        raise StudentNotInSchoolError(f"Aluno não encontrado nesta escola: {student_id}")

    existing = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id, Enrollment.classroom_id == classroom.id)
        .first()
    )
    if existing is not None:
        raise AlreadyEnrolledError("Este aluno já está matriculado nesta turma.")

    enrollment = Enrollment(student_id=student_id, classroom_id=classroom.id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def assign_teacher(db: Session, school_id: uuid.UUID, classroom_id: uuid.UUID, teacher_id: uuid.UUID) -> TeacherClassroomAssignment:
    classroom = get_classroom_in_school(db, school_id, classroom_id)

    teacher = (
        db.query(User)
        .filter(User.id == teacher_id, User.school_id == school_id, User.role.has(name=RoleName.PROFESSOR))
        .first()
    )
    if teacher is None:
        raise TeacherNotInSchoolError(f"Professor não encontrado nesta escola: {teacher_id}")

    existing = (
        db.query(TeacherClassroomAssignment)
        .filter(TeacherClassroomAssignment.teacher_id == teacher_id, TeacherClassroomAssignment.classroom_id == classroom.id)
        .first()
    )
    if existing is not None:
        raise AlreadyAssignedError("Este professor já está atribuído a esta turma.")

    assignment = TeacherClassroomAssignment(teacher_id=teacher_id, classroom_id=classroom.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment
