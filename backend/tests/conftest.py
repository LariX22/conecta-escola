"""Fixtures compartilhadas dos testes: banco SQLite em memória e cliente de API.

Usamos SQLite em memória para os testes automatizados rodarem rápido e
sem depender de um PostgreSQL disponível. O comportamento de SQL
específico do Postgres (ex.: tipos nativos) é evitado nos modelos
testados aqui; a validação completa com Postgres acontece via Docker
Compose + Alembic, conforme documentado no README.
"""
from types import SimpleNamespace

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


@pytest.fixture(autouse=True, scope="session")
def fast_password_hashing():
    """Reduz o custo do bcrypt nos testes (muitos usuários e logins por teste).

    Em produção continua valendo o custo padrão do passlib.
    """
    from app.core import security

    security._pwd_context.update(bcrypt__rounds=4)


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


def build_school_scenario(client) -> SimpleNamespace:
    """Escola com turmas 5A e 5B, um professor e um responsável por turma.

    Há também um responsável sem aluno vinculado e um usuário com papel de aluno.
    Atributos: `admin`, `direcao`, `secretaria`, `coordenacao`, `prof_a`, `prof_b`,
    `resp_a`, `resp_b`, `resp_livre` e `aluno` são tokens de acesso; os mesmos nomes
    com sufixo `_id` são os ids dos usuários; `class_a`/`class_b` são ids de turmas.
    """
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school_id = create_school(client, admin)["id"]

    def user(email: str, role: str) -> str:
        return register_and_login(client, email, role, school_id=school_id)

    s = SimpleNamespace(
        school_id=school_id,
        admin=admin,
        direcao=user("direcao@escola.com", "direcao"),
        secretaria=user("secretaria@escola.com", "secretaria"),
        coordenacao=user("coord@escola.com", "coordenacao_pedagogica"),
        prof_a=user("prof-a@escola.com", "professor"),
        prof_b=user("prof-b@escola.com", "professor"),
        resp_a=user("resp-a@escola.com", "responsavel"),
        resp_b=user("resp-b@escola.com", "responsavel"),
        resp_livre=user("resp-livre@escola.com", "responsavel"),
        aluno=user("aluno@escola.com", "aluno"),
    )

    def user_id(token: str) -> str:
        return client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).json()["id"]

    for name in ("direcao", "secretaria", "coordenacao", "prof_a", "prof_b", "resp_a", "resp_b", "resp_livre", "aluno"):
        setattr(s, f"{name}_id", user_id(getattr(s, name)))

    def post(path: str, payload: dict) -> dict:
        response = client.post(path, json=payload, headers={"Authorization": "Bearer " + s.secretaria})
        assert response.status_code == 201, response.text
        return response.json()

    s.class_a = post("/api/v1/classrooms", {"name": "5A", "segment": "Fundamental", "school_year": 2026})["id"]
    s.class_b = post("/api/v1/classrooms", {"name": "5B", "segment": "Fundamental", "school_year": 2026})["id"]
    student_a = post("/api/v1/students", {"full_name": "Aluno A"})["id"]
    student_b = post("/api/v1/students", {"full_name": "Aluno B"})["id"]

    post(f"/api/v1/classrooms/{s.class_a}/enrollments", {"student_id": student_a})
    post(f"/api/v1/classrooms/{s.class_b}/enrollments", {"student_id": student_b})
    post(f"/api/v1/students/{student_a}/guardians", {"guardian_id": s.resp_a_id, "relationship_label": "mae"})
    post(f"/api/v1/students/{student_b}/guardians", {"guardian_id": s.resp_b_id, "relationship_label": "pai"})
    post(f"/api/v1/classrooms/{s.class_a}/teachers", {"teacher_id": s.prof_a_id})
    post(f"/api/v1/classrooms/{s.class_b}/teachers", {"teacher_id": s.prof_b_id})
    return s


def create_school(client, admin_token: str, name: str = "Escola Teste", slug: str = "escola-teste") -> dict:
    response = client.post(
        "/api/v1/schools",
        json={"name": name, "slug": slug},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()
