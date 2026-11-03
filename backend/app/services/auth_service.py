"""Regras de negócio de autenticação: registro e login de usuários.

Mantidas fora das rotas para que possam ser testadas e reutilizadas
sem depender do framework web.
"""
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Role, RoleName, User
from app.schemas.auth import UserRegisterRequest


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRoleError(Exception):
    pass


def register_user(db: Session, data: UserRegisterRequest) -> User:
    """Cria o usuário sem checar permissões de quem está criando.

    Uso interno (bootstrap do admin inicial, `user_service` e testes).
    Nunca exponha esta função diretamente em uma rota: use
    `user_service.create_user_as`, que aplica a matriz de permissões.
    """
    if db.query(User).filter(User.email == data.email).first():
        raise EmailAlreadyRegisteredError(f"E-mail já cadastrado: {data.email}")

    try:
        role_name = RoleName(data.role)
    except ValueError as exc:
        raise InvalidRoleError(f"Papel inválido: {data.role}") from exc

    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role_id=role.id,
        school_id=data.school_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("E-mail ou senha inválidos.")
    if not user.is_active:
        raise InvalidCredentialsError("Usuário inativo.")
    return user


def build_access_token_for_user(user: User) -> str:
    extra_claims = {"role": user.role.name.value}
    if user.school_id:
        extra_claims["school_id"] = str(user.school_id)
    return create_access_token(subject=str(user.id), extra_claims=extra_claims)
