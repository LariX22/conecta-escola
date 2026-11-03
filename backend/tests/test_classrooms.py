"""Testes de turmas, matrículas e atribuições de professores."""
from tests.conftest import create_school, register_and_login


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_secretaria_can_create_classroom_and_enroll_student(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])

    classroom = client.post(
        "/api/v1/classrooms",
        json={"name": "5A", "segment": "Ensino Fundamental", "school_year": 2026},
        headers=_auth_header(secretaria_token),
    )
    assert classroom.status_code == 201
    classroom_id = classroom.json()["id"]

    student = client.post(
        "/api/v1/students", json={"full_name": "Aluno da Turma"}, headers=_auth_header(secretaria_token)
    ).json()

    enrollment = client.post(
        f"/api/v1/classrooms/{classroom_id}/enrollments",
        json={"student_id": student["id"]},
        headers=_auth_header(secretaria_token),
    )
    assert enrollment.status_code == 201
    assert enrollment.json()["classroom_id"] == classroom_id


def test_cannot_create_duplicate_classroom_same_year(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])

    payload = {"name": "5A", "segment": "Ensino Fundamental", "school_year": 2026}
    first = client.post("/api/v1/classrooms", json=payload, headers=_auth_header(secretaria_token))
    assert first.status_code == 201
    second = client.post("/api/v1/classrooms", json=payload, headers=_auth_header(secretaria_token))
    assert second.status_code == 409


def test_teacher_only_sees_assigned_classrooms(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin_token)
    secretaria_token = register_and_login(client, "secretaria@escola.com", "secretaria", school_id=school["id"])
    professor_token = register_and_login(client, "professor@escola.com", "professor", school_id=school["id"])

    classroom_a = client.post(
        "/api/v1/classrooms",
        json={"name": "5A", "segment": "Fundamental", "school_year": 2026},
        headers=_auth_header(secretaria_token),
    ).json()
    client.post(
        "/api/v1/classrooms",
        json={"name": "5B", "segment": "Fundamental", "school_year": 2026},
        headers=_auth_header(secretaria_token),
    )

    professor_me = client.get("/api/v1/auth/me", headers=_auth_header(professor_token)).json()

    assign_response = client.post(
        f"/api/v1/classrooms/{classroom_a['id']}/teachers",
        json={"teacher_id": professor_me["id"]},
        headers=_auth_header(secretaria_token),
    )
    assert assign_response.status_code == 201

    list_response = client.get("/api/v1/classrooms", headers=_auth_header(professor_token))
    assert list_response.status_code == 200
    classrooms = list_response.json()
    assert len(classrooms) == 1
    assert classrooms[0]["id"] == classroom_a["id"]


def test_cannot_enroll_student_from_another_school(client):
    admin_token = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school_a = create_school(client, admin_token, name="Escola A", slug="escola-a")
    school_b = create_school(client, admin_token, name="Escola B", slug="escola-b")

    secretaria_a = register_and_login(client, "secretaria-a@escola.com", "secretaria", school_id=school_a["id"])
    secretaria_b = register_and_login(client, "secretaria-b@escola.com", "secretaria", school_id=school_b["id"])

    classroom_a = client.post(
        "/api/v1/classrooms",
        json={"name": "5A", "segment": "Fundamental", "school_year": 2026},
        headers=_auth_header(secretaria_a),
    ).json()
    student_b = client.post(
        "/api/v1/students", json={"full_name": "Aluno da Escola B"}, headers=_auth_header(secretaria_b)
    ).json()

    # A secretaria da escola A tenta matricular um aluno que pertence à escola B.
    response = client.post(
        f"/api/v1/classrooms/{classroom_a['id']}/enrollments",
        json={"student_id": student_b["id"]},
        headers=_auth_header(secretaria_a),
    )
    assert response.status_code == 404
