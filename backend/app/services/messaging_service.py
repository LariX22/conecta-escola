"""Regras de negócio para mensagens privadas (conversas 1:1).

Quem pode falar com quem (decidido no servidor, sempre dentro da mesma escola):
- Direção, secretaria e coordenação: com qualquer funcionário e qualquer responsável.
- Professores: com os demais funcionários e com os responsáveis de alunos
  matriculados em turmas às quais estão atribuídos.
- Responsáveis: com direção, secretaria, coordenação e com os professores das
  turmas dos seus filhos. Nunca com outros responsáveis.
- Alunos e administrador técnico: sem acesso nesta fase.

Só os dois participantes leem uma conversa. A regra de contato também é conferida
a cada mensagem enviada: se algo mudar (ex.: o filho trocou de turma), novas
mensagens são bloqueadas, mas o histórico continua visível aos dois.
"""
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, joinedload

from app.core.timeutils import as_utc, utc_now
from app.models.classroom import Enrollment, TeacherClassroomAssignment
from app.models.conversation import Conversation, ConversationParticipant, Message
from app.models.student import StudentGuardianLink
from app.models.user import Role, RoleName, User
from app.schemas.message import ContactResponse, ConversationResponse, MessageResponse

MANAGEMENT_ROLES = (RoleName.DIRECAO, RoleName.SECRETARIA, RoleName.COORDENACAO_PEDAGOGICA)
STAFF_ROLES = MANAGEMENT_ROLES + (RoleName.PROFESSOR,)
MAX_CONTACTS = 200


class RecipientNotFoundError(Exception):
    pass


class MessagingNotAllowedError(Exception):
    pass


class ConversationNotFoundError(Exception):
    pass


def _contacts_query(db: Session, me: User) -> Query:
    """Usuários com quem `me` pode conversar. Fonte única da regra de contato."""
    role = me.role.name
    if me.school_id is None or (role not in STAFF_ROLES and role is not RoleName.RESPONSAVEL):
        raise MessagingNotAllowedError("Este perfil ainda não usa mensagens.")

    base = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.school_id == me.school_id, User.is_active.is_(True), User.id != me.id)
    )
    staff = User.role.has(Role.name.in_(STAFF_ROLES))

    if role in MANAGEMENT_ROLES:
        return base.filter(or_(staff, User.role.has(name=RoleName.RESPONSAVEL)))

    if role is RoleName.PROFESSOR:
        guardians_of_my_students = (
            select(StudentGuardianLink.guardian_id)
            .join(Enrollment, Enrollment.student_id == StudentGuardianLink.student_id)
            .join(TeacherClassroomAssignment, TeacherClassroomAssignment.classroom_id == Enrollment.classroom_id)
            .where(TeacherClassroomAssignment.teacher_id == me.id, Enrollment.is_active.is_(True))
        )
        return base.filter(or_(staff, User.id.in_(guardians_of_my_students)))

    teachers_of_my_children = (
        select(TeacherClassroomAssignment.teacher_id)
        .join(Enrollment, Enrollment.classroom_id == TeacherClassroomAssignment.classroom_id)
        .join(StudentGuardianLink, StudentGuardianLink.student_id == Enrollment.student_id)
        .where(StudentGuardianLink.guardian_id == me.id, Enrollment.is_active.is_(True))
    )
    return base.filter(or_(User.role.has(Role.name.in_(MANAGEMENT_ROLES)), User.id.in_(teachers_of_my_children)))


def list_contacts(db: Session, me: User, search: str | None = None) -> list[User]:
    query = _contacts_query(db, me)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(User.full_name.ilike(f"%{escaped}%", escape="\\"))
    return query.order_by(User.full_name).limit(MAX_CONTACTS).all()


def _direct_key(first_id: uuid.UUID, second_id: uuid.UUID) -> str:
    low, high = sorted((str(first_id), str(second_id)))
    return f"{low}:{high}"


def get_or_create_direct_conversation(db: Session, me: User, recipient_id: uuid.UUID) -> tuple[Conversation, bool]:
    """Abre (ou reaproveita) a conversa direta com o destinatário. Retorna (conversa, criada_agora)."""
    recipient = (
        db.query(User)
        .filter(User.id == recipient_id, User.school_id == me.school_id, User.is_active.is_(True))
        .first()
    )
    if recipient is None or recipient.id == me.id:
        raise RecipientNotFoundError(f"Destinatário não encontrado: {recipient_id}")
    if _contacts_query(db, me).filter(User.id == recipient.id).first() is None:
        raise MessagingNotAllowedError("Você não pode enviar mensagens para este usuário.")

    key = _direct_key(me.id, recipient.id)
    existing = db.query(Conversation).filter(Conversation.direct_key == key).first()
    if existing is not None:
        return existing, False

    conversation = Conversation(school_id=me.school_id, direct_key=key)
    conversation.participants = [ConversationParticipant(user_id=me.id), ConversationParticipant(user_id=recipient.id)]
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        # Duas aberturas simultâneas do mesmo par: fica a conversa que chegou primeiro.
        db.rollback()
        return db.query(Conversation).filter(Conversation.direct_key == key).one(), False
    db.refresh(conversation)
    return conversation, True


def get_conversation_for(db: Session, me: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = (
        db.query(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .filter(
            Conversation.id == conversation_id,
            Conversation.school_id == me.school_id,
            ConversationParticipant.user_id == me.id,
        )
        .first()
    )
    if conversation is None:
        raise ConversationNotFoundError(f"Conversa não encontrada: {conversation_id}")
    return conversation


def _participant(conversation: Conversation, user_id: uuid.UUID) -> ConversationParticipant:
    return next(p for p in conversation.participants if p.user_id == user_id)


def _other_participant(conversation: Conversation, user_id: uuid.UUID) -> ConversationParticipant:
    return next(p for p in conversation.participants if p.user_id != user_id)


def participant_ids(conversation: Conversation) -> list[uuid.UUID]:
    return [p.user_id for p in conversation.participants]


def build_message_response(conversation: Conversation, message: Message) -> MessageResponse:
    recipient = _other_participant(conversation, message.sender_id)
    read = recipient.last_read_at is not None and as_utc(recipient.last_read_at) >= as_utc(message.created_at)
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
        read_by_recipient=read,
    )


def _unread_count(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID, last_read_at: datetime | None) -> int:
    query = db.query(func.count(Message.id)).filter(Message.conversation_id == conversation_id, Message.sender_id != user_id)
    if last_read_at is not None:
        query = query.filter(Message.created_at > last_read_at)
    return query.scalar() or 0


def build_conversation_response(db: Session, me: User, conversation: Conversation) -> ConversationResponse:
    other = _other_participant(conversation, me.id).user
    last = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    return ConversationResponse(
        id=conversation.id,
        other_user=ContactResponse(id=other.id, full_name=other.full_name, role=other.role.name.value),
        last_message=build_message_response(conversation, last) if last is not None else None,
        unread_count=_unread_count(db, conversation.id, me.id, _participant(conversation, me.id).last_read_at),
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
    )


def list_conversations(db: Session, me: User, limit: int = 100) -> list[Conversation]:
    """Conversas do usuário que já têm mensagens, da mais recente para a mais antiga."""
    return (
        db.query(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .filter(
            ConversationParticipant.user_id == me.id,
            Conversation.school_id == me.school_id,
            Conversation.last_message_at.is_not(None),
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(limit)
        .all()
    )


def list_messages(
    db: Session, me: User, conversation_id: uuid.UUID, limit: int, before: datetime | None
) -> tuple[Conversation, list[Message]]:
    """Mensagens em ordem cronológica. `before` pagina para trás (mensagens mais antigas)."""
    conversation = get_conversation_for(db, me, conversation_id)
    query = db.query(Message).filter(Message.conversation_id == conversation.id)
    if before is not None:
        query = query.filter(Message.created_at < as_utc(before))
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    messages.reverse()
    return conversation, messages


def send_message(db: Session, me: User, conversation_id: uuid.UUID, body: str) -> tuple[Conversation, Message]:
    conversation = get_conversation_for(db, me, conversation_id)
    other_id = _other_participant(conversation, me.id).user_id
    if _contacts_query(db, me).filter(User.id == other_id).first() is None:
        raise MessagingNotAllowedError("Você não pode mais enviar mensagens para este usuário.")

    now = utc_now()
    message = Message(conversation_id=conversation.id, sender_id=me.id, body=body, created_at=now)
    conversation.last_message_at = now
    _participant(conversation, me.id).last_read_at = now  # quem escreve já leu tudo até aqui
    db.add(message)
    db.commit()
    db.refresh(message)
    db.refresh(conversation)
    return conversation, message


def mark_read(db: Session, me: User, conversation_id: uuid.UUID) -> tuple[Conversation, datetime]:
    conversation = get_conversation_for(db, me, conversation_id)
    now = utc_now()
    _participant(conversation, me.id).last_read_at = now
    db.commit()
    db.refresh(conversation)
    return conversation, now
