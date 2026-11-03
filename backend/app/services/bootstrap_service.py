"""Criação do primeiro administrador técnico a partir de variáveis de ambiente.

Como não há cadastro público, alguém precisa criar a primeira conta que
depois cadastra escolas e demais usuários.
"""
import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.user import RoleName, User
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import register_user

logger = logging.getLogger(__name__)


def ensure_bootstrap_admin(db: Session, email: str, password: str, full_name: str) -> User | None:
    """Cria o administrador técnico inicial se o e-mail ainda não existir.

    Retorna o usuário criado ou None quando nada foi feito. Nunca altera
    um usuário existente (nem a senha): a variável de ambiente não pode ser
    usada para sobrescrever contas já criadas.
    """
    try:
        data = UserRegisterRequest(
            full_name=full_name, email=email, password=password, role=RoleName.ADMIN_TECNICO.value
        )
    except ValidationError as exc:
        # Não registrar `input`: ele conteria a senha.
        problems = ", ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        logger.error("Variáveis BOOTSTRAP_ADMIN_* inválidas (%s); administrador não criado.", problems)
        return None

    if db.query(User).filter(User.email == data.email).first() is not None:
        return None

    user = register_user(db, data)
    logger.info("Administrador técnico inicial criado: %s", user.email)
    return user
