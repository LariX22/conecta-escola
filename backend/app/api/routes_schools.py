"""Rotas de escolas (tenants).

Apenas o administrador técnico cria escolas. Demais papéis podem
consultar apenas a própria escola (reforço de isolamento multi-tenant).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.school import SchoolCreateRequest, SchoolResponse
from app.services.school_service import SlugAlreadyExistsError, create_school, get_school

router = APIRouter(prefix="/schools", tags=["schools"])


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
def create_school_route(
    payload: SchoolCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin_tecnico")),
) -> SchoolResponse:
    try:
        school = create_school(db, payload)
    except SlugAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SchoolResponse.model_validate(school)


@router.get("/{school_id}", response_model=SchoolResponse)
def get_school_route(
    school_id,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SchoolResponse:
    is_admin = current_user.role.name.value == "admin_tecnico"
    if not is_admin and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não tem permissão para acessar esta escola.",
        )

    school = get_school(db, school_id)
    if school is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escola não encontrada.")
    return SchoolResponse.model_validate(school)
