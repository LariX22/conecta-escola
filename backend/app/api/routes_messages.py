"""Rotas de mensagens privadas: REST e canal em tempo real (WebSocket).

Regras de contato e de acesso estão em `messaging_service` (decididas no
servidor). Resumo: só os dois participantes leem uma conversa, e responsável
nunca conversa com outro responsável.

Tempo real: o cliente abre `/ws/messages` e envia, como primeira mensagem,
`{"type": "auth", "token": "<JWT>"}` (o token não vai na URL, para não aparecer
em logs). Depois recebe eventos `message` e `read` das suas conversas. Enviar
`{"type": "ping"}` devolve `{"type": "pong"}`. O envio continua sendo feito
pela API REST; o WebSocket só entrega eventos.
"""
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from pydantic import AwareDatetime
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import require_roles
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import RoleName, User
from app.schemas.message import (
    ContactResponse,
    ConversationCreateRequest,
    ConversationResponse,
    MessageCreateRequest,
    MessageResponse,
)
from app.services.messaging_service import (
    MANAGEMENT_ROLES,
    ConversationNotFoundError,
    MessagingNotAllowedError,
    RecipientNotFoundError,
    build_conversation_response,
    build_message_response,
    get_or_create_direct_conversation,
    list_contacts,
    list_conversations,
    list_messages,
    mark_read,
    participant_ids,
    send_message,
)
from app.services.realtime import manager, notify_users

router = APIRouter(prefix="/messages", tags=["messages"])
ws_router = APIRouter(tags=["messages"])

_MESSAGING_ROLES = ("direcao", "secretaria", "coordenacao_pedagogica", "professor", "responsavel")
_ALLOWED_SOCKET_ROLES = MANAGEMENT_ROLES + (RoleName.PROFESSOR, RoleName.RESPONSAVEL)

AUTH_TIMEOUT_SECONDS = 10
WS_UNSUPPORTED_DATA = 1003
WS_POLICY_VIOLATION = 1008


def _forbidden(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/contacts", response_model=list[ContactResponse])
def list_contacts_route(
    q: str | None = Query(default=None, max_length=100, description="Filtra pelo nome"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> list[ContactResponse]:
    try:
        contacts = list_contacts(db, current_user, q)
    except MessagingNotAllowedError as exc:
        raise _forbidden(exc) from exc
    return [ContactResponse(id=u.id, full_name=u.full_name, role=u.role.name.value) for u in contacts]


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def open_conversation_route(
    payload: ConversationCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> ConversationResponse:
    """Abre a conversa com o destinatário. 201 se for nova; 200 se já existia."""
    try:
        conversation, created = get_or_create_direct_conversation(db, current_user, payload.recipient_id)
    except RecipientNotFoundError as exc:
        raise _not_found(exc) from exc
    except MessagingNotAllowedError as exc:
        raise _forbidden(exc) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return build_conversation_response(db, current_user, conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> list[ConversationResponse]:
    conversations = list_conversations(db, current_user)
    return [build_conversation_response(db, current_user, c) for c in conversations]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages_route(
    conversation_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: AwareDatetime | None = Query(default=None, description="Traz só mensagens anteriores a este instante"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> list[MessageResponse]:
    try:
        conversation, messages = list_messages(db, current_user, conversation_id, limit, before)
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    return [build_message_response(conversation, m) for m in messages]


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def send_message_route(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> MessageResponse:
    try:
        conversation, message = send_message(db, current_user, conversation_id, payload.body)
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    except MessagingNotAllowedError as exc:
        raise _forbidden(exc) from exc

    result = build_message_response(conversation, message)
    # Também vai para quem enviou, para atualizar as outras abas/dispositivos dela.
    notify_users(
        participant_ids(conversation),
        {"type": "message", "conversation_id": str(conversation.id), "message": result.model_dump(mode="json")},
    )
    return result


@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read_route(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MESSAGING_ROLES)),
) -> None:
    """Marca a conversa como lida até agora (zera as não lidas e avisa a outra pessoa)."""
    try:
        conversation, read_at = mark_read(db, current_user, conversation_id)
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    notify_users(
        participant_ids(conversation),
        {
            "type": "read",
            "conversation_id": str(conversation.id),
            "reader_id": str(current_user.id),
            "read_at": read_at.isoformat(),
        },
    )


def _user_id_for_token(db: Session, token: object) -> uuid.UUID | None:
    """Valida o token e devolve o id do usuário, ou None se não puder usar mensagens."""
    try:
        if not isinstance(token, str):
            return None
        payload = decode_access_token(token)
        if payload is None or "sub" not in payload:
            return None
        user = db.query(User).filter(User.id == uuid.UUID(payload["sub"])).first()
        if user is None or not user.is_active or user.school_id is None or user.role.name not in _ALLOWED_SOCKET_ROLES:
            return None
        return user.id
    except ValueError:
        return None
    finally:
        db.rollback()  # encerra a transação: a conexão volta ao pool e não fica presa ao WebSocket


async def _close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except Exception:
        pass


async def _authenticate_socket(websocket: WebSocket, db: Session) -> uuid.UUID | None:
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, KeyError):
        await _close(websocket, WS_POLICY_VIOLATION)
        return None

    token = first.get("token") if isinstance(first, dict) and first.get("type") == "auth" else None
    user_id = await run_in_threadpool(_user_id_for_token, db, token)
    if user_id is None:
        await _close(websocket, WS_POLICY_VIOLATION)
    return user_id


@ws_router.websocket("/ws/messages")
async def messages_socket(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    await websocket.accept()
    user_id = await _authenticate_socket(websocket, db)
    if user_id is None:
        return

    manager.connect(user_id, websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            message = await websocket.receive_json()
            if isinstance(message, dict) and message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except (ValueError, KeyError):
        await _close(websocket, WS_UNSUPPORTED_DATA)
    finally:
        manager.disconnect(user_id, websocket)
