"""Rotas de usuários.

Não existe cadastro público: apenas administrador técnico, direção e
secretaria criam contas, e cada um só pode criar determinados papéis
(a matriz completa está em `app.services.user_service`).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserRegisterRequest, UserResponse
from app.services.auth_service import EmailAlreadyRegisteredError, InvalidRoleError
from app.services.user_service import (
    InvalidSchoolAssignmentError,
    SchoolNotFoundError,
    UserCreationNotAllowedError,
    create_user_as,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin_tecnico", "direcao", "secretaria")),
) -> UserResponse:
    try:
        user = create_user_as(db, current_user, payload)
    except UserCreationNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (InvalidRoleError, InvalidSchoolAssignmentError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserResponse.from_user(user)
