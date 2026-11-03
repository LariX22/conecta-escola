"""Testes da criação de usuários: matriz de permissões e isolamento entre escolas."""
import uuid

from app.models.user import User
from app.services.bootstrap_service import ensure_bootstrap_admin
from tests.conftest import create_school, register_and_login


def _auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _new_user(email: str, role: str, school_id: str | None = None, password: str = "SenhaForte123") -> dict:
    payload = {"full_name": "Fulano de Tal", "email": email, "password": password, "role": role}
    if school_id is not None:
        payload["school_id"] = school_id
    return payload


def _create(client, token: str, payload: dict):
    return client.post("/api/v1/users", json=payload, headers=_auth(token))


def test_creating_users_requires_authentication(client):
    response = client.post("/api/v1/users", json=_new_user("a@escola.com", "professor"))
    assert response.status_code == 401


def test_admin_tecnico_creates_direcao_for_a_school(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)

    response = _create(client, admin, _new_user("diretora@escola.com", "direcao", school["id"]))

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "direcao"
    assert body["school_id"] == school["id"]
    assert "password" not in body and "hashed_password" not in body


def test_admin_tecnico_must_inform_school_for_school_roles(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    response = _create(client, admin, _new_user("diretora@escola.com", "direcao"))
    assert response.status_code == 422


def test_admin_tecnico_cannot_use_unknown_school(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    response = _create(client, admin, _new_user("diretora@escola.com", "direcao", str(uuid.uuid4())))
    assert response.status_code == 404


def test_admin_tecnico_can_create_another_admin_but_without_school(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)

    ok = _create(client, admin, _new_user("admin2@conecta.com", "admin_tecnico"))
    assert ok.status_code == 201
    assert ok.json()["school_id"] is None

    with_school = _create(client, admin, _new_user("admin3@conecta.com", "admin_tecnico", school["id"]))
    assert with_school.status_code == 422


def test_direcao_creates_users_only_in_own_school(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school_a = create_school(client, admin, name="Escola A", slug="escola-a")
    school_b = create_school(client, admin, name="Escola B", slug="escola-b")
    direcao_a = register_and_login(client, "direcao-a@escola.com", "direcao", school_id=school_a["id"])

    # Sem informar a escola, o usuário nasce na escola de quem criou.
    implicit = _create(client, direcao_a, _new_user("prof@escola.com", "professor"))
    assert implicit.status_code == 201
    assert implicit.json()["school_id"] == school_a["id"]

    explicit = _create(client, direcao_a, _new_user("sec@escola.com", "secretaria", school_a["id"]))
    assert explicit.status_code == 201

    other_school = _create(client, direcao_a, _new_user("intruso@escola.com", "professor", school_b["id"]))
    assert other_school.status_code == 403


def test_direcao_cannot_create_direcao_or_admin_tecnico(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)
    direcao = register_and_login(client, "direcao@escola.com", "direcao", school_id=school["id"])

    assert _create(client, direcao, _new_user("outra@escola.com", "direcao")).status_code == 403
    assert _create(client, direcao, _new_user("root@escola.com", "admin_tecnico")).status_code == 403


def test_secretaria_creates_teachers_guardians_and_students_only(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)
    secretaria = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])

    assert _create(client, secretaria, _new_user("prof@escola.com", "professor")).status_code == 201
    assert _create(client, secretaria, _new_user("resp@escola.com", "responsavel")).status_code == 201
    assert _create(client, secretaria, _new_user("aluno@escola.com", "aluno")).status_code == 201

    assert _create(client, secretaria, _new_user("sec2@escola.com", "secretaria")).status_code == 403
    assert _create(client, secretaria, _new_user("coord@escola.com", "coordenacao_pedagogica")).status_code == 403
    assert _create(client, secretaria, _new_user("dir@escola.com", "direcao")).status_code == 403


def test_other_roles_cannot_create_users(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)

    for role in ("professor", "coordenacao_pedagogica", "responsavel", "aluno"):
        token = register_and_login(client, f"{role}@escola.com", role, school_id=school["id"])
        response = _create(client, token, _new_user(f"novo-{role}@escola.com", "responsavel"))
        assert response.status_code == 403, role


def test_duplicate_email_is_rejected(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)
    payload = _new_user("diretora@escola.com", "direcao", school["id"])

    assert _create(client, admin, payload).status_code == 201
    assert _create(client, admin, payload).status_code == 409


def test_invalid_role_and_weak_password_are_rejected(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)

    invalid_role = _create(client, admin, _new_user("a@escola.com", "super_admin", school["id"]))
    assert invalid_role.status_code == 422

    weak_password = _create(client, admin, _new_user("b@escola.com", "direcao", school["id"], password="curta"))
    assert weak_password.status_code == 422


def test_created_user_can_login(client):
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)
    _create(client, admin, _new_user("diretora@escola.com", "direcao", school["id"], password="OutraSenha123"))

    response = client.post("/api/v1/auth/login", json={"email": "diretora@escola.com", "password": "OutraSenha123"})
    assert response.status_code == 200


def test_bootstrap_admin_is_created_once_and_never_overwritten(client):
    created = ensure_bootstrap_admin(client.db_session, "admin@escola.com", "SenhaForte123", "Admin Inicial")
    assert created is not None
    assert created.role.name.value == "admin_tecnico"
    assert created.school_id is None

    again = ensure_bootstrap_admin(client.db_session, "admin@escola.com", "OutraSenha123", "Outro Nome")
    assert again is None

    ok = client.post("/api/v1/auth/login", json={"email": "admin@escola.com", "password": "SenhaForte123"})
    assert ok.status_code == 200
    changed = client.post("/api/v1/auth/login", json={"email": "admin@escola.com", "password": "OutraSenha123"})
    assert changed.status_code == 401


def test_bootstrap_admin_with_weak_password_is_not_created(client):
    assert ensure_bootstrap_admin(client.db_session, "admin@escola.com", "curta", "Admin Inicial") is None
    assert client.db_session.query(User).count() == 0
