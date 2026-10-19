"""Importa todos os modelos para que o Alembic/SQLAlchemy os conheça.

Ao criar um novo modelo, adicione o import aqui para que as migrações
autogeradas o detectem.
"""
from app.db.session import Base  # noqa: F401
from app.models.school import School  # noqa: F401
from app.models.user import Role, User  # noqa: F401
