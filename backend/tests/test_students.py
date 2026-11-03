"""Testes de alunos: permissões por papel e isolamento multi-tenant."""
from tests.conftest import create_school, register_and_login


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_secretaria_can_create_and_list_students(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])

    create_response = client.post(
        "/api/v1/students", json={"full_name": "João Aluno"}, headers=_auth_header(secretaria_token)
    )
    assert create_response.status_code == 201
    assert create_response.json()["school_id"] == school["id"]

    list_response = client.get("/api/v1/students", headers=_auth_header(secretaria_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_professor_can_list_but_not_create_students(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    professor_token = register_and_login(client, "professor@escola.com", "professor", school_id=school["id"])

    create_response = client.post(
        "/api/v1/students", json={"full_name": "João Aluno"}, headers=_auth_header(professor_token)
    )
    assert create_response.status_code == 403

    list_response = client.get("/api/v1/students", headers=_auth_header(professor_token))
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_students_are_isolated_between_schools(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school_a = create_school(client, admin_token, name="Escola A", slug="escola-a")
    school_b = create_school(client, admin_token, name="Escola B", slug="escola-b")

    secretaria_a = register_and_login(client, "secretaria-a@escola.com", "secretaria", school_id=school_a["id"])
    secretaria_b = register_and_login(client, "secretaria-b@escola.com", "secretaria", school_id=school_b["id"])

    create_response = client.post(
        "/api/v1/students", json={"full_name": "Aluno da Escola A"}, headers=_auth_header(secretaria_a)
    )
    student_id = create_response.json()["id"]

    # A secretaria da escola B não enxerga o aluno da escola A.
    get_response = client.get(f"/api/v1/students/{student_id}", headers=_auth_header(secretaria_b))
    assert get_response.status_code == 404

    list_response = client.get("/api/v1/students", headers=_auth_header(secretaria_b))
    assert list_response.json() == []


def test_guardian_can_only_see_linked_students(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])
    guardian_token = register_and_login(client, "responsavel@escola.com", "responsavel", school_id=school["id"])

    student_1 = client.post(
        "/api/v1/students", json={"full_name": "Filho Vinculado"}, headers=_auth_header(secretaria_token)
    ).json()
    student_2 = client.post(
        "/api/v1/students", json={"full_name": "Outro Aluno"}, headers=_auth_header(secretaria_token)
    ).json()

    guardian_me = client.get("/api/v1/auth/me", headers=_auth_header(guardian_token)).json()

    link_response = client.post(
        f"/api/v1/students/{student_1['id']}/guardians",
        json={"guardian_id": guardian_me["id"], "relationship_label": "mae"},
        headers=_auth_header(secretaria_token),
    )
    assert link_response.status_code == 201

    list_response = client.get("/api/v1/students", headers=_auth_header(guardian_token))
    assert list_response.status_code == 200
    ids = [s["id"] for s in list_response.json()]
    assert student_1["id"] in ids
    assert student_2["id"] not in ids

    # O responsável não consegue consultar um aluno ao qual não está vinculado.
    forbidden_response = client.get(f"/api/v1/students/{student_2['id']}", headers=_auth_header(guardian_token))
    assert forbidden_response.status_code == 403


def test_cannot_link_guardian_twice(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])
    guardian_token = register_and_login(client, "responsavel@escola.com", "responsavel", school_id=school["id"])

    student = client.post(
        "/api/v1/students", json={"full_name": "Aluno"}, headers=_auth_header(secretaria_token)
    ).json()
    guardian_me = client.get("/api/v1/auth/me", headers=_auth_header(guardian_token)).json()

    payload = {"guardian_id": guardian_me["id"], "relationship_label": "pai"}
    first = client.post(
        f"/api/v1/students/{student['id']}/guardians", json=payload, headers=_auth_header(secretaria_token)
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/students/{student['id']}/guardians", json=payload, headers=_auth_header(secretaria_token)
    )
    assert second.status_code == 409
