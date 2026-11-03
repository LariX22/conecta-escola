"""Regras de negócio para criação de usuários por usuários autorizados.

Não existe cadastro público: toda conta é criada por alguém com permissão.

Quem pode criar quem:
- admin_tecnico: qualquer papel (papéis de escola exigem `school_id`).
- direcao: secretaria, professor, coordenacao_pedagogica, responsavel e
  aluno, sempre na própria escola.
- secretaria: professor, responsavel e aluno, sempre na própria escola.
Os demais papéis não criam usuários.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.school import School
from app.models.user import RoleName, User
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import InvalidRoleError, register_user


class UserCreationNotAllowedError(Exception):
    pass


class InvalidSchoolAssignmentError(Exception):
    pass


class SchoolNotFoundError(Exception):
    pass


_CREATABLE_ROLES: dict[RoleName, frozenset[RoleName]] = {
    RoleName.ADMIN_TECNICO: frozenset(RoleName),
    RoleName.DIRECAO: frozenset(
        {
            RoleName.SECRETARIA,
            RoleName.PROFESSOR,
            RoleName.COORDENACAO_PEDAGOGICA,
            RoleName.RESPONSAVEL,
            RoleName.ALUNO,
        }
    ),
    RoleName.SECRETARIA: frozenset({RoleName.PROFESSOR, RoleName.RESPONSAVEL, RoleName.ALUNO}),
}


def create_user_as(db: Session, creator: User, data: UserRegisterRequest) -> User:
    try:
        target_role = RoleName(data.role)
    except ValueError as exc:
        raise InvalidRoleError(f"Papel inválido: {data.role}") from exc

    allowed_roles = _CREATABLE_ROLES.get(creator.role.name, frozenset())
    if target_role not in allowed_roles:
        raise UserCreationNotAllowedError(
            f"Seu perfil não pode criar usuários com o papel '{target_role.value}'."
        )

    school_id = _resolve_school_id(db, creator, target_role, data.school_id)
    return register_user(db, data.model_copy(update={"school_id": school_id}))


def _resolve_school_id(
    db: Session, creator: User, target_role: RoleName, requested_school_id: uuid.UUID | None
) -> uuid.UUID | None:
    if target_role is RoleName.ADMIN_TECNICO:
        if requested_school_id is not None:
            raise InvalidSchoolAssignmentError("O administrador técnico não pertence a nenhuma escola.")
        return None

    if creator.role.name is RoleName.ADMIN_TECNICO:
        if requested_school_id is None:
            raise InvalidSchoolAssignmentError("Informe o school_id da escola do novo usuário.")
        if db.query(School).filter(School.id == requested_school_id).first() is None:
            raise SchoolNotFoundError(f"Escola não encontrada: {requested_school_id}")
        return requested_school_id

    if creator.school_id is None:
        raise UserCreationNotAllowedError("Seu usuário não está vinculado a nenhuma escola.")
    if requested_school_id is not None and requested_school_id != creator.school_id:
        raise UserCreationNotAllowedError("Não é possível criar usuários em outra escola.")
    return creator.school_id
