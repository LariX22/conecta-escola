"""Testes de login, usuário autenticado e ausência de cadastro público."""
from tests.conftest import create_user_directly

PASSWORD = "SenhaForte123"


def _login(client, email: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_public_registration_is_not_available(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invasor",
            "email": "invasor@escola.com",
            "password": PASSWORD,
            "role": "admin_tecnico",
        },
    )
    assert response.status_code == 404


def test_login_with_correct_credentials_returns_token(client):
    create_user_directly(client, "professor@escola.com", "professor")
    response = _login(client, "professor@escola.com")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


def test_login_with_wrong_password_is_rejected(client):
    create_user_directly(client, "professor@escola.com", "professor")
    response = _login(client, "professor@escola.com", password="senha-errada")
    assert response.status_code == 401


def test_login_rejects_inactive_user(client):
    user = create_user_directly(client, "professor@escola.com", "professor")
    user.is_active = False
    client.db_session.commit()
    assert _login(client, "professor@escola.com").status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client):
    create_user_directly(client, "professor@escola.com", "professor")
    token = _login(client, "professor@escola.com").json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert response.json()["email"] == "professor@escola.com"


def test_token_of_deactivated_user_is_rejected(client):
    user = create_user_directly(client, "professor@escola.com", "professor")
    token = _login(client, "professor@escola.com").json()["access_token"]

    user.is_active = False
    client.db_session.commit()

    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
