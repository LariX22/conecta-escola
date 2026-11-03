"""Fixtures compartilhadas dos testes: banco SQLite em memória e cliente de API.

Usamos SQLite em memória para os testes automatizados rodarem rápido e
sem depender de um PostgreSQL disponível. O comportamento de SQL
específico do Postgres (ex.: tipos nativos) é evitado nos modelos
testados aqui; a validação completa com Postgres acontece via Docker
Compose + Alembic, conforme documentado no README.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import register_user


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.db_session = db_session
        yield test_client
    app.dependency_overrides.clear()


def create_user_directly(client, email: str, role: str, school_id: str | None = None, password: str = "SenhaForte123"):
    """Cria um usuário direto no banco de testes, sem passar por permissões.

    Não existe cadastro público na API; os testes usam este atalho para
    montar o cenário inicial (ex.: o primeiro admin_tecnico).
    """
    return register_user(
        client.db_session,
        UserRegisterRequest(
            full_name=f"Usuário {role}", email=email, password=password, role=role, school_id=school_id
        ),
    )


def register_and_login(client, email: str, role: str, school_id: str | None = None, password: str = "SenhaForte123") -> str:
    """Cria um usuário com o papel informado e retorna o token de acesso.

    Função utilitária compartilhada pelos testes de cadastros, que
    precisam de múltiplos usuários (direção, secretaria, professor,
    responsável, etc.) vinculados a uma mesma escola.
    """
    create_user_directly(client, email, role, school_id=school_id, password=password)

    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["access_token"]


def create_school(client, admin_token: str, name: str = "Escola Teste", slug: str = "escola-teste") -> dict:
    response = client.post(
        "/api/v1/schools",
        json={"name": name, "slug": slug},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()
