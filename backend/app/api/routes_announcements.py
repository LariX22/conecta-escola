"""Rotas de comunicados e confirmação de leitura.

Regras de acesso (decididas no servidor; detalhes em `announcement_service`):
- Direção, secretaria e coordenação pedagógica: publicam para a escola
  inteira ou para qualquer turma da escola, e veem/gerenciam todos os
  comunicados da própria escola.
- Professores: publicam apenas para turmas às quais estão atribuídos e só
  editam/apagam o que escreveram.
- Responsáveis: leem os comunicados endereçados a eles e confirmam a leitura.
- Alunos e administrador técnico: sem acesso nesta fase.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles, require_school_id
from app.db.session import get_db
from app.models.announcement import Announcement
from app.models.user import RoleName, User
from app.schemas.announcement import (
    AnnouncementCreateRequest,
    AnnouncementReadReport,
    AnnouncementReadResponse,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
)
from app.services.announcement_service import (
    AnnouncementNotFoundError,
    AnnouncementPermissionError,
    build_read_report,
    build_response,
    confirm_read,
    create_announcement,
    delete_announcement,
    get_announcement,
    get_read_map,
    list_announcements,
    update_announcement,
)
from app.services.classroom_service import ClassroomNotFoundError

router = APIRouter(prefix="/announcements", tags=["announcements"])

_AUTHOR_ROLES = ("direcao", "secretaria", "coordenacao_pedagogica", "professor")


def _forbidden(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _responses_for(db: Session, user: User, announcements: list[Announcement]) -> list[AnnouncementResponse]:
    """Monta as respostas, incluindo `my_read_at` quando quem consulta é um responsável."""
    read_map = {}
    if user.role.name is RoleName.RESPONSAVEL:
        read_map = get_read_map(db, user.id, [announcement.id for announcement in announcements])
    return [build_response(announcement, read_map.get(announcement.id)) for announcement in announcements]


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement_route(
    payload: AnnouncementCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_AUTHOR_ROLES)),
) -> AnnouncementResponse:
    require_school_id(current_user)
    try:
        announcement = create_announcement(db, current_user, payload)
    except ClassroomNotFoundError as exc:
        raise _not_found(exc) from exc
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    return build_response(announcement)


@router.get("", response_model=list[AnnouncementResponse])
def list_announcements_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AnnouncementResponse]:
    try:
        announcements = list_announcements(db, current_user)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    return _responses_for(db, current_user, announcements)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement_route(
    announcement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnnouncementResponse:
    try:
        announcement = get_announcement(db, current_user, announcement_id)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    except AnnouncementNotFoundError as exc:
        raise _not_found(exc) from exc
    return _responses_for(db, current_user, [announcement])[0]


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement_route(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_AUTHOR_ROLES)),
) -> AnnouncementResponse:
    try:
        announcement = update_announcement(db, current_user, announcement_id, payload)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    except AnnouncementNotFoundError as exc:
        raise _not_found(exc) from exc
    return build_response(announcement)


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement_route(
    announcement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_AUTHOR_ROLES)),
) -> None:
    try:
        delete_announcement(db, current_user, announcement_id)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    except AnnouncementNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/{announcement_id}/read", response_model=AnnouncementReadResponse, status_code=status.HTTP_201_CREATED)
def confirm_read_route(
    announcement_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnnouncementReadResponse:
    """Confirma a leitura. 201 na primeira vez; 200 (mesmos dados) se já havia confirmação."""
    try:
        read, created = confirm_read(db, current_user, announcement_id)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    except AnnouncementNotFoundError as exc:
        raise _not_found(exc) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return AnnouncementReadResponse.model_validate(read)


@router.get("/{announcement_id}/reads", response_model=AnnouncementReadReport)
def read_report_route(
    announcement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnnouncementReadReport:
    try:
        return build_read_report(db, current_user, announcement_id)
    except AnnouncementPermissionError as exc:
        raise _forbidden(exc) from exc
    except AnnouncementNotFoundError as exc:
        raise _not_found(exc) from exc
