"""Rotas de alunos e vínculos com responsáveis.

Regras de acesso (reforçadas no servidor, não apenas ocultadas na UI):
- Direção e secretaria: podem criar, listar, consultar e editar alunos
  da própria escola, e vincular responsáveis.
- Professores e coordenação pedagógica: podem listar e consultar
  alunos da própria escola (somente leitura nesta fase).
- Responsáveis: podem listar e consultar apenas os alunos aos quais
  estejam vinculados.
- Alunos: ainda não possuem rota própria nesta fase (limitação
  conhecida, a ser tratada em uma etapa futura com um recurso "meus
  dados").
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles, require_school_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.student import (
    GuardianLinkCreateRequest,
    GuardianLinkResponse,
    StudentCreateRequest,
    StudentResponse,
    StudentUpdateRequest,
)
from app.services.student_service import (
    GuardianAlreadyLinkedError,
    GuardianNotFoundError,
    StudentNotFoundError,
    create_student,
    get_student_in_school,
    guardian_has_access_to_student,
    link_guardian,
    list_students_for_guardian,
    list_students_for_school,
    update_student,
)

router = APIRouter(prefix="/students", tags=["students"])

_STAFF_READ_ROLES = ("direcao", "secretaria", "professor", "coordenacao_pedagogica")
_STAFF_WRITE_ROLES = ("direcao", "secretaria")


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student_route(
    payload: StudentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> StudentResponse:
    school_id = require_school_id(current_user)
    student = create_student(db, school_id, payload)
    return StudentResponse.model_validate(student)


@router.get("", response_model=list[StudentResponse])
def list_students_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StudentResponse]:
    role = current_user.role.name.value
    if role in _STAFF_READ_ROLES:
        school_id = require_school_id(current_user)
        students = list_students_for_school(db, school_id)
    elif role == "responsavel":
        students = list_students_for_guardian(db, current_user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este perfil ainda não tem acesso à listagem de alunos.",
        )
    return [StudentResponse.model_validate(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
def get_student_route(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudentResponse:
    role = current_user.role.name.value
    if role in _STAFF_READ_ROLES:
        school_id = require_school_id(current_user)
        try:
            student = get_student_in_school(db, school_id, student_id)
        except StudentNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    elif role == "responsavel":
        if not guardian_has_access_to_student(db, current_user.id, student_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não está vinculado a este aluno.",
            )
        try:
            student = get_student_in_school(db, current_user.school_id, student_id)
        except StudentNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este perfil ainda não tem acesso a esta informação.",
        )
    return StudentResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student_route(
    student_id: uuid.UUID,
    payload: StudentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> StudentResponse:
    school_id = require_school_id(current_user)
    try:
        student = update_student(db, school_id, student_id, payload)
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StudentResponse.model_validate(student)


@router.post("/{student_id}/guardians", response_model=GuardianLinkResponse, status_code=status.HTTP_201_CREATED)
def link_guardian_route(
    student_id: uuid.UUID,
    payload: GuardianLinkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_STAFF_WRITE_ROLES)),
) -> GuardianLinkResponse:
    school_id = require_school_id(current_user)
    try:
        link = link_guardian(db, school_id, student_id, payload.guardian_id, payload.relationship_label)
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GuardianNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GuardianAlreadyLinkedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return GuardianLinkResponse.model_validate(link)
