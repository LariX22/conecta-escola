"""Regras de negócio para comunicados e confirmação de leitura.

Todas as consultas filtram explicitamente por `school_id`, e a visibilidade
é decidida aqui (no servidor), nunca pela interface:

- Direção, secretaria e coordenação pedagógica: veem todos os comunicados
  da própria escola, inclusive os agendados.
- Professores: veem os que escreveram e os já publicados para a escola
  inteira ou para turmas às quais estão atribuídos.
- Responsáveis: veem apenas os já publicados para a escola inteira ou
  para turmas onde um aluno vinculado a eles tem matrícula ativa.
- Alunos e administrador técnico: sem acesso nesta fase.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from app.models.announcement import (
    AUDIENCE_CLASSROOMS,
    AUDIENCE_SCHOOL,
    Announcement,
    AnnouncementClassroom,
    AnnouncementRead,
)
from app.models.classroom import Classroom, Enrollment, TeacherClassroomAssignment
from app.models.student import StudentGuardianLink
from app.models.user import RoleName, User
from app.schemas.announcement import (
    AnnouncementCreateRequest,
    AnnouncementReadReport,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
    RecipientReadStatus,
)
from app.services.classroom_service import ClassroomNotFoundError

MANAGEMENT_ROLES = frozenset({RoleName.DIRECAO, RoleName.SECRETARIA, RoleName.COORDENACAO_PEDAGOGICA})


class AnnouncementNotFoundError(Exception):
    pass


class AnnouncementPermissionError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normaliza para UTC. Valores sem fuso (ex.: lidos do SQLite) são tratados como UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def announcement_status(announcement: Announcement) -> str:
    return "published" if _as_utc(announcement.publish_at) <= _now() else "scheduled"


def build_response(announcement: Announcement, my_read_at: datetime | None = None) -> AnnouncementResponse:
    return AnnouncementResponse(
        id=announcement.id,
        school_id=announcement.school_id,
        author_id=announcement.author_id,
        author_name=announcement.author.full_name,
        title=announcement.title,
        body=announcement.body,
        audience=announcement.audience,
        classroom_ids=[target.classroom_id for target in announcement.targets],
        requires_confirmation=announcement.requires_confirmation,
        publish_at=announcement.publish_at,
        status=announcement_status(announcement),
        created_at=announcement.created_at,
        updated_at=announcement.updated_at,
        my_read_at=my_read_at,
    )


def create_announcement(db: Session, author: User, data: AnnouncementCreateRequest) -> Announcement:
    school_id = author.school_id
    role = author.role.name
    classroom_ids = list(dict.fromkeys(data.classroom_ids))

    if data.audience == AUDIENCE_SCHOOL:
        if role not in MANAGEMENT_ROLES:
            raise AnnouncementPermissionError("Professores só podem enviar comunicados para as próprias turmas.")
    else:
        found = {
            row[0]
            for row in db.query(Classroom.id).filter(Classroom.school_id == school_id, Classroom.id.in_(classroom_ids))
        }
        for classroom_id in classroom_ids:
            if classroom_id not in found:
                raise ClassroomNotFoundError(f"Turma não encontrada nesta escola: {classroom_id}")

        if role is RoleName.PROFESSOR:
            assigned = {
                row[0]
                for row in db.query(TeacherClassroomAssignment.classroom_id).filter(
                    TeacherClassroomAssignment.teacher_id == author.id,
                    TeacherClassroomAssignment.classroom_id.in_(classroom_ids),
                )
            }
            if not set(classroom_ids) <= assigned:
                raise AnnouncementPermissionError(
                    "Você só pode enviar comunicados para turmas às quais está atribuído."
                )

    announcement = Announcement(
        school_id=school_id,
        author_id=author.id,
        title=data.title,
        body=data.body,
        audience=data.audience,
        requires_confirmation=data.requires_confirmation,
        publish_at=_as_utc(data.publish_at) if data.publish_at else _now(),
    )
    announcement.targets = [AnnouncementClassroom(classroom_id=classroom_id) for classroom_id in classroom_ids]
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


def _addressed_to(classroom_ids) -> object:
    """Condição: comunicado para a escola toda ou para alguma das turmas informadas."""
    return or_(
        Announcement.audience == AUDIENCE_SCHOOL,
        Announcement.id.in_(
            select(AnnouncementClassroom.announcement_id).where(AnnouncementClassroom.classroom_id.in_(classroom_ids))
        ),
    )


def _visible_query(db: Session, user: User) -> Query:
    role = user.role.name
    if user.school_id is None or (role not in MANAGEMENT_ROLES and role not in (RoleName.PROFESSOR, RoleName.RESPONSAVEL)):
        raise AnnouncementPermissionError("Este perfil ainda não tem acesso aos comunicados.")

    query = db.query(Announcement).filter(Announcement.school_id == user.school_id)
    if role in MANAGEMENT_ROLES:
        return query

    published = Announcement.publish_at <= _now()
    if role is RoleName.PROFESSOR:
        teacher_classrooms = select(TeacherClassroomAssignment.classroom_id).where(
            TeacherClassroomAssignment.teacher_id == user.id
        )
        return query.filter(or_(Announcement.author_id == user.id, and_(published, _addressed_to(teacher_classrooms))))

    guardian_classrooms = (
        select(Enrollment.classroom_id)
        .join(StudentGuardianLink, StudentGuardianLink.student_id == Enrollment.student_id)
        .where(StudentGuardianLink.guardian_id == user.id, Enrollment.is_active.is_(True))
    )
    return query.filter(published, _addressed_to(guardian_classrooms))


def list_announcements(db: Session, user: User) -> list[Announcement]:
    return _visible_query(db, user).order_by(Announcement.publish_at.desc(), Announcement.created_at.desc()).all()


def get_announcement(db: Session, user: User, announcement_id: uuid.UUID) -> Announcement:
    announcement = _visible_query(db, user).filter(Announcement.id == announcement_id).first()
    if announcement is None:
        raise AnnouncementNotFoundError(f"Comunicado não encontrado: {announcement_id}")
    return announcement


def get_read_map(db: Session, user_id: uuid.UUID, announcement_ids: list[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    rows = db.query(AnnouncementRead.announcement_id, AnnouncementRead.read_at).filter(
        AnnouncementRead.user_id == user_id, AnnouncementRead.announcement_id.in_(announcement_ids)
    )
    return {announcement_id: read_at for announcement_id, read_at in rows}


def confirm_read(db: Session, user: User, announcement_id: uuid.UUID) -> tuple[AnnouncementRead, bool]:
    """Registra a confirmação de leitura. Retorna (registro, criado_agora); é idempotente."""
    if user.role.name is not RoleName.RESPONSAVEL:
        raise AnnouncementPermissionError("Somente responsáveis confirmam a leitura de comunicados.")

    announcement = get_announcement(db, user, announcement_id)
    query = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == announcement.id, AnnouncementRead.user_id == user.id
    )
    existing = query.first()
    if existing is not None:
        return existing, False

    read = AnnouncementRead(announcement_id=announcement.id, user_id=user.id)
    db.add(read)
    try:
        db.commit()
    except IntegrityError:
        # Duas confirmações simultâneas: vale a que chegou primeiro.
        db.rollback()
        return query.one(), False
    db.refresh(read)
    return read, True


def list_recipient_guardians(db: Session, announcement: Announcement) -> list[User]:
    query = db.query(User).filter(
        User.school_id == announcement.school_id,
        User.is_active.is_(True),
        User.role.has(name=RoleName.RESPONSAVEL),
    )
    if announcement.audience == AUDIENCE_CLASSROOMS:
        classroom_ids = [target.classroom_id for target in announcement.targets]
        guardian_ids = (
            select(StudentGuardianLink.guardian_id)
            .join(Enrollment, Enrollment.student_id == StudentGuardianLink.student_id)
            .where(Enrollment.classroom_id.in_(classroom_ids), Enrollment.is_active.is_(True))
        )
        query = query.filter(User.id.in_(guardian_ids))
    return query.order_by(User.full_name).all()


def _ensure_can_manage(user: User, announcement: Announcement) -> None:
    if user.role.name in MANAGEMENT_ROLES or announcement.author_id == user.id:
        return
    raise AnnouncementPermissionError("Somente o autor ou a gestão da escola podem fazer isso.")


def build_read_report(db: Session, user: User, announcement_id: uuid.UUID) -> AnnouncementReadReport:
    announcement = get_announcement(db, user, announcement_id)
    _ensure_can_manage(user, announcement)

    guardians = list_recipient_guardians(db, announcement)
    read_map = {
        read.user_id: read.read_at
        for read in db.query(AnnouncementRead).filter(AnnouncementRead.announcement_id == announcement.id)
    }
    recipients = [
        RecipientReadStatus(guardian_id=g.id, guardian_name=g.full_name, read_at=read_map.get(g.id)) for g in guardians
    ]
    read_count = sum(1 for recipient in recipients if recipient.read_at is not None)
    return AnnouncementReadReport(
        announcement_id=announcement.id,
        requires_confirmation=announcement.requires_confirmation,
        recipient_count=len(recipients),
        read_count=read_count,
        pending_count=len(recipients) - read_count,
        recipients=recipients,
    )


def update_announcement(
    db: Session, user: User, announcement_id: uuid.UUID, data: AnnouncementUpdateRequest
) -> Announcement:
    announcement = get_announcement(db, user, announcement_id)
    _ensure_can_manage(user, announcement)
    if data.title is not None:
        announcement.title = data.title
    if data.body is not None:
        announcement.body = data.body
    db.commit()
    db.refresh(announcement)
    return announcement


def delete_announcement(db: Session, user: User, announcement_id: uuid.UUID) -> None:
    announcement = get_announcement(db, user, announcement_id)
    _ensure_can_manage(user, announcement)
    db.delete(announcement)
    db.commit()
