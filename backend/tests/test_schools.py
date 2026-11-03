"""Testes de escolas: criação restrita a admin_tecnico e isolamento multi-tenant."""
from tests.conftest import create_school, register_and_login


def test_user_can_read_own_school_and_admin_can_read_any(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token, name="Escola A", slug="escola-a")
    direcao_token = register_and_login(client, "direcao-a@escola.com", "direcao", school_id=school["id"])

    own = client.get(f"/api/v1/schools/{school['id']}", headers={"Authorization": "Bearer " + direcao_token})
    assert own.status_code == 200
    assert own.json()["id"] == school["id"]

    as_admin = client.get(f"/api/v1/schools/{school['id']}", headers={"Authorization": "Bearer " + admin_token})
    assert as_admin.status_code == 200


def test_only_admin_tecnico_can_create_school(client):
    register_and_login(client, "professor@escola.com", "professor")
    professor_login = client.post(
        "/api/v1/auth/login", json={"email": "professor@escola.com", "password": "SenhaForte123"}
    ).json()
    response = client.post(
        "/api/v1/schools",
        json={"name": "Escola X", "slug": "escola-x"},
        headers={"Authorization": f"Bearer {professor_login['access_token']}"},
    )
    assert response.status_code == 403


def test_admin_tecnico_can_create_school(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    assert school["slug"] == "escola-teste"
    assert school["is_active"] is True


def test_cannot_create_school_with_duplicate_slug(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    create_school(client, admin_token)
    response = client.post(
        "/api/v1/schools",
        json={"name": "Outra Escola", "slug": "escola-teste"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


def test_user_cannot_read_another_schools_data(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school_a = create_school(client, admin_token, name="Escola A", slug="escola-a")
    school_b = create_school(client, admin_token, name="Escola B", slug="escola-b")

    token_a = register_and_login(client, "direcao-a@escola.com", "direcao", school_id=school_a["id"])

    response = client.get(
        f"/api/v1/schools/{school_b['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 403
