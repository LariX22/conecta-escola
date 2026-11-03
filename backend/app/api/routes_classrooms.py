"""Rotas de turmas, matrículas e atribuições de professores.

Regras de acesso:
- Direção e secretaria: podem criar turmas, matricular alunos e
  atribuir professores, dentro da própria escola.
- Coordenação pedagógica: pode listar as turmas da própria escola
  (somente leitura nesta fase).
- Professores: só enxergam as turmas às quais estão atribuídos — nunca
  todas as turmas da escola.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles, require_school_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.classroom import (
    ClassroomCreateRequest,
    ClassroomResponse,
    EnrollmentCreateRequest,
    EnrollmentResponse,
    TeacherAssignmentCreateRequest,
    TeacherAssignmentResponse,
)
from app.services.classroom_service import (
    AlreadyAssignedError,
    AlreadyEnrolledError,
    ClassroomAlreadyExistsError,
    ClassroomNotFoundError,
    StudentNotInSchoolError,
    TeacherNotInSchoolError,
    assign_teacher,
    create_classroom,
    enroll_student,
    list_classrooms_for_school,
    list_classrooms_for_teacher,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])

_STAFF_WRITE_ROLES = ("direcao", "secretaria")


@router.post("", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
def create_classroom_route(
    payload: ClassroomCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> ClassroomResponse:
    school_id = require_school_id(current_user)
    try:
        classroom = create_classroom(db, school_id, payload)
    except ClassroomAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ClassroomResponse.model_validate(classroom)


@router.get("", response_model=list[ClassroomResponse])
def list_classrooms_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ClassroomResponse]:
    role = current_user.role.name.value
    if role in ("direcao", "secretaria", "coordenacao_pedagogica"):
        school_id = require_school_id(current_user)
        classrooms = list_classrooms_for_school(db, school_id)
    elif role == "professor":
        classrooms = list_classrooms_for_teacher(db, current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este perfil ainda não tem acesso à listagem de turmas.",
        )
    return [ClassroomResponse.model_validate(c) for c in classrooms]


@router.post("/{classroom_id}/enrollments", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_student_route(
    classroom_id: uuid.UUID,
    payload: EnrollmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> EnrollmentResponse:
    school_id = require_school_id(current_user)
    try:
        enrollment = enroll_student(db, school_id, classroom_id, payload.student_id)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StudentNotInSchoolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyEnrolledError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return EnrollmentResponse.model_validate(enrollment)


@router.post("/{classroom_id}/teachers", response_model=TeacherAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_teacher_route(
    classroom_id: uuid.UUID,
    payload: TeacherAssignmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> TeacherAssignmentResponse:
    school_id = require_school_id(current_user)
    try:
        assignment = assign_teacher(db, school_id, classroom_id, payload.teacher_id)
    except ClassroomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TeacherNotInSchoolError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TeacherAssignmentResponse.model_validate(assignment)
