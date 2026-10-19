"""Testes das regras críticas de autenticação e permissões."""


def _register_payload(email: str = "professor@escola.com", role: str = "professor") -> dict:
    return {
        "full_name": "Maria Professora",
        "email": email,
        "password": "SenhaForte123",
        "role": role,
    }


def test_register_creates_user(client):
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "professor@escola.com"
    assert body["role"] == "professor"
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_rejects_duplicate_email(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post("/api/v1/auth/register", json=_register_payload())
    assert response.status_code == 409


def test_register_rejects_invalid_role(client):
    response = client.post("/api/v1/auth/register", json=_register_payload(role="super_admin_invalido"))
    assert response.status_code == 422


def test_login_with_correct_credentials_returns_token(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "professor@escola.com", "password": "SenhaForte123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


def test_login_with_wrong_password_is_rejected(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "professor@escola.com", "password": "senha-errada"},
    )
    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client):
    client.post("/api/v1/auth/register", json=_register_payload())
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "professor@escola.com", "password": "SenhaForte123"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "professor@escola.com"
