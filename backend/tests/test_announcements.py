"""Testes de comunicados: público-alvo, agendamento, confirmação de leitura e permissões."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.announcement import AnnouncementClassroom, AnnouncementRead
from app.models.classroom import Enrollment
from tests.conftest import create_school, register_and_login


def _auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _setup(client) -> SimpleNamespace:
    """Escola com turmas 5A e 5B, um professor e um responsável por turma.

    Há também um responsável sem aluno vinculado e um usuário com papel de aluno.
    """
    admin = register_and_login(client, "admin@conecta.com", "admin_tecnico")
    school = create_school(client, admin)
    school_id = school["id"]

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
        return client.get("/api/v1/auth/me", headers=_auth(token)).json()["id"]

    def post(path: str, payload: dict) -> dict:
        response = client.post(path, json=payload, headers=_auth(s.secretaria))
        assert response.status_code == 201, response.text
        return response.json()

    s.class_a = post("/api/v1/classrooms", {"name": "5A", "segment": "Fundamental", "school_year": 2026})["id"]
    s.class_b = post("/api/v1/classrooms", {"name": "5B", "segment": "Fundamental", "school_year": 2026})["id"]
    student_a = post("/api/v1/students", {"full_name": "Aluno A"})["id"]
    student_b = post("/api/v1/students", {"full_name": "Aluno B"})["id"]

    post(f"/api/v1/classrooms/{s.class_a}/enrollments", {"student_id": student_a})
    post(f"/api/v1/classrooms/{s.class_b}/enrollments", {"student_id": student_b})
    s.resp_a_id = user_id(s.resp_a)
    s.resp_b_id = user_id(s.resp_b)
    post(f"/api/v1/students/{student_a}/guardians", {"guardian_id": s.resp_a_id, "relationship_label": "mae"})
    post(f"/api/v1/students/{student_b}/guardians", {"guardian_id": s.resp_b_id, "relationship_label": "pai"})
    post(f"/api/v1/classrooms/{s.class_a}/teachers", {"teacher_id": user_id(s.prof_a)})
    post(f"/api/v1/classrooms/{s.class_b}/teachers", {"teacher_id": user_id(s.prof_b)})
    return s


def _publish(client, token: str, **overrides):
    payload = {"title": "Reunião de pais", "body": "Sexta-feira, às 19h.", "audience": "school"}
    payload.update(overrides)
    return client.post("/api/v1/announcements", json=payload, headers=_auth(token))


def _list(client, token: str) -> list[dict]:
    response = client.get("/api/v1/announcements", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def _titles(client, token: str) -> list[str]:
    return [item["title"] for item in _list(client, token)]


def test_management_roles_publish_to_the_whole_school(client):
    s = _setup(client)
    for token in (s.direcao, s.secretaria, s.coordenacao):
        response = _publish(client, token)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["audience"] == "school"
        assert body["classroom_ids"] == []
        assert body["status"] == "published"
        assert body["school_id"] == s.school_id


def test_school_wide_announcement_reaches_all_guardians_and_teachers(client):
    s = _setup(client)
    _publish(client, s.direcao, title="Recesso")
    for token in (s.resp_a, s.resp_b, s.resp_livre, s.prof_a, s.prof_b, s.direcao):
        assert _titles(client, token) == ["Recesso"]


def test_classroom_announcement_reaches_only_target_audience(client):
    s = _setup(client)
    created = _publish(
        client, s.secretaria, title="Passeio 5A", audience="classrooms", classroom_ids=[s.class_a, s.class_a]
    ).json()
    assert created["classroom_ids"] == [s.class_a]  # turma repetida entra uma vez só

    for token in (s.resp_a, s.prof_a, s.direcao):
        assert _titles(client, token) == ["Passeio 5A"]
    assert client.get(f"/api/v1/announcements/{created['id']}", headers=_auth(s.resp_a)).status_code == 200

    for token in (s.resp_b, s.resp_livre, s.prof_b):
        assert _titles(client, token) == []
        assert client.get(f"/api/v1/announcements/{created['id']}", headers=_auth(token)).status_code == 404


def test_teacher_publishes_only_to_assigned_classrooms(client):
    s = _setup(client)
    assert _publish(client, s.prof_a, audience="classrooms", classroom_ids=[s.class_a]).status_code == 201
    assert _publish(client, s.prof_a, audience="classrooms", classroom_ids=[s.class_b]).status_code == 403
    assert _publish(client, s.prof_a, audience="classrooms", classroom_ids=[s.class_a, s.class_b]).status_code == 403
    assert _publish(client, s.prof_a).status_code == 403  # escola inteira é só para a gestão


def test_announcements_are_isolated_between_schools(client):
    s = _setup(client)
    school_b = create_school(client, s.admin, name="Escola B", slug="escola-b")
    direcao_b = register_and_login(client, "direcao-b@escola.com", "direcao", school_id=school_b["id"])
    classroom_b = client.post(
        "/api/v1/classrooms",
        json={"name": "9A", "segment": "Fundamental", "school_year": 2026},
        headers=_auth(direcao_b),
    ).json()["id"]
    created = _publish(client, s.direcao).json()
    url = f"/api/v1/announcements/{created['id']}"

    # A direção da escola A não consegue endereçar uma turma da escola B.
    assert _publish(client, s.direcao, audience="classrooms", classroom_ids=[classroom_b]).status_code == 404

    # A direção da escola B não enxerga nem mexe em nada da escola A.
    assert _titles(client, direcao_b) == []
    assert client.get(url, headers=_auth(direcao_b)).status_code == 404
    assert client.get(url + "/reads", headers=_auth(direcao_b)).status_code == 404
    assert client.patch(url, json={"title": "Invasão"}, headers=_auth(direcao_b)).status_code == 404
    assert client.delete(url, headers=_auth(direcao_b)).status_code == 404
    assert _titles(client, s.direcao) == ["Reunião de pais"]


def test_guardians_cannot_publish_and_unsupported_roles_have_no_access(client):
    s = _setup(client)
    assert _publish(client, s.resp_a).status_code == 403
    assert _publish(client, s.aluno).status_code == 403
    assert _publish(client, s.admin).status_code == 403
    for token in (s.aluno, s.admin):
        assert client.get("/api/v1/announcements", headers=_auth(token)).status_code == 403
    assert client.get("/api/v1/announcements").status_code == 401


def test_scheduled_announcement_is_hidden_from_guardians_until_publish_time(client):
    s = _setup(client)
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    created = _publish(
        client, s.prof_a, title="Em breve", audience="classrooms", classroom_ids=[s.class_a], publish_at=future
    ).json()
    assert created["status"] == "scheduled"
    url = f"/api/v1/announcements/{created['id']}"

    assert _titles(client, s.resp_a) == []
    assert client.get(url, headers=_auth(s.resp_a)).status_code == 404
    assert client.post(url + "/read", headers=_auth(s.resp_a)).status_code == 404

    # O autor e a gestão enxergam o comunicado agendado.
    for token in (s.prof_a, s.direcao):
        assert [(i["title"], i["status"]) for i in _list(client, token)] == [("Em breve", "scheduled")]


def test_publish_at_honors_time_zone_and_past_dates_publish_immediately(client):
    s = _setup(client)
    brasilia = timezone(timedelta(hours=-3))
    future_local = (datetime.now(brasilia) + timedelta(hours=2)).isoformat()
    past_local = (datetime.now(timezone(timedelta(hours=5))) - timedelta(hours=1)).isoformat()

    assert _publish(client, s.direcao, title="Futuro", publish_at=future_local).json()["status"] == "scheduled"
    assert _publish(client, s.direcao, title="Passado", publish_at=past_local).json()["status"] == "published"
    assert _titles(client, s.resp_a) == ["Passado"]


def test_publish_at_requires_a_time_zone(client):
    s = _setup(client)
    assert _publish(client, s.direcao, publish_at="2030-01-01T10:00:00").status_code == 422


def test_guardian_confirms_reading_once_and_it_is_idempotent(client):
    s = _setup(client)
    created = _publish(
        client, s.secretaria, audience="classrooms", classroom_ids=[s.class_a], requires_confirmation=True
    ).json()
    url = f"/api/v1/announcements/{created['id']}/read"

    first = client.post(url, headers=_auth(s.resp_a))
    assert first.status_code == 201
    second = client.post(url, headers=_auth(s.resp_a))
    assert second.status_code == 200
    assert second.json()["read_at"] == first.json()["read_at"]
    assert second.json()["user_id"] == s.resp_a_id

    assert _list(client, s.resp_a)[0]["my_read_at"] is not None
    assert _list(client, s.direcao)[0]["my_read_at"] is None
    assert client.db_session.query(AnnouncementRead).count() == 1


def test_only_addressed_guardians_can_confirm_reading(client):
    s = _setup(client)
    created = _publish(client, s.secretaria, audience="classrooms", classroom_ids=[s.class_a]).json()
    url = f"/api/v1/announcements/{created['id']}/read"

    assert client.post(url, headers=_auth(s.resp_b)).status_code == 404  # filho em outra turma
    assert client.post(url, headers=_auth(s.resp_livre)).status_code == 404
    for token in (s.direcao, s.prof_a, s.aluno):
        assert client.post(url, headers=_auth(token)).status_code == 403
    assert client.db_session.query(AnnouncementRead).count() == 0


def test_read_report_counts_confirmations_for_management_and_author(client):
    s = _setup(client)
    created = _publish(
        client, s.prof_a, audience="classrooms", classroom_ids=[s.class_a], requires_confirmation=True
    ).json()
    url = f"/api/v1/announcements/{created['id']}"

    report = client.get(url + "/reads", headers=_auth(s.prof_a)).json()
    assert (report["recipient_count"], report["read_count"], report["pending_count"]) == (1, 0, 1)
    assert report["requires_confirmation"] is True
    assert report["recipients"][0]["guardian_id"] == s.resp_a_id
    assert report["recipients"][0]["read_at"] is None

    client.post(url + "/read", headers=_auth(s.resp_a))
    report = client.get(url + "/reads", headers=_auth(s.direcao)).json()
    assert (report["recipient_count"], report["read_count"], report["pending_count"]) == (1, 1, 0)
    assert report["recipients"][0]["read_at"] is not None

    assert client.get(url + "/reads", headers=_auth(s.resp_a)).status_code == 403
    assert client.get(url + "/reads", headers=_auth(s.prof_b)).status_code == 404  # nem enxerga o comunicado


def test_school_wide_report_lists_every_guardian_and_hides_from_non_authors(client):
    s = _setup(client)
    created = _publish(client, s.direcao).json()
    url = f"/api/v1/announcements/{created['id']}/reads"

    report = client.get(url, headers=_auth(s.direcao)).json()
    assert report["recipient_count"] == 3
    names = [r["guardian_name"] for r in report["recipients"]]
    assert names == sorted(names)

    # O professor enxerga o comunicado geral, mas não o relatório (não é o autor).
    assert client.get(url, headers=_auth(s.prof_a)).status_code == 403


def test_inactive_enrollment_removes_guardian_from_classroom_audience(client):
    s = _setup(client)
    created = _publish(client, s.secretaria, title="5A", audience="classrooms", classroom_ids=[s.class_a]).json()
    assert _titles(client, s.resp_a) == ["5A"]

    client.db_session.query(Enrollment).filter(Enrollment.classroom_id == uuid.UUID(s.class_a)).update(
        {"is_active": False}
    )
    client.db_session.commit()

    assert _titles(client, s.resp_a) == []
    report = client.get(f"/api/v1/announcements/{created['id']}/reads", headers=_auth(s.direcao)).json()
    assert report["recipient_count"] == 0


def test_author_and_management_can_edit_and_delete(client):
    s = _setup(client)
    created = _publish(
        client, s.prof_a, title="Original", audience="classrooms", classroom_ids=[s.class_a]
    ).json()
    url = f"/api/v1/announcements/{created['id']}"

    edited = client.patch(url, json={"title": "Corrigido"}, headers=_auth(s.prof_a))
    assert edited.status_code == 200
    assert edited.json()["title"] == "Corrigido"
    assert client.patch(url, json={"body": "Novo texto"}, headers=_auth(s.direcao)).json()["body"] == "Novo texto"
    assert client.patch(url, json={}, headers=_auth(s.prof_a)).status_code == 422

    assert client.patch(url, json={"title": "X"}, headers=_auth(s.resp_a)).status_code == 403
    assert client.delete(url, headers=_auth(s.resp_a)).status_code == 403
    assert client.patch(url, json={"title": "X"}, headers=_auth(s.prof_b)).status_code == 404

    client.post(url + "/read", headers=_auth(s.resp_a))
    assert client.delete(url, headers=_auth(s.direcao)).status_code == 204
    assert client.get(url, headers=_auth(s.direcao)).status_code == 404
    assert client.db_session.query(AnnouncementRead).count() == 0
    assert client.db_session.query(AnnouncementClassroom).count() == 0


def test_teacher_cannot_edit_or_delete_announcement_written_by_someone_else(client):
    s = _setup(client)
    created = _publish(client, s.direcao).json()
    url = f"/api/v1/announcements/{created['id']}"

    assert client.get(url, headers=_auth(s.prof_a)).status_code == 200
    assert client.patch(url, json={"title": "X"}, headers=_auth(s.prof_a)).status_code == 403
    assert client.delete(url, headers=_auth(s.prof_a)).status_code == 403


def test_announcement_payload_validation(client):
    s = _setup(client)
    assert _publish(client, s.direcao, audience="classrooms").status_code == 422  # sem turmas
    assert _publish(client, s.direcao, classroom_ids=[s.class_a]).status_code == 422  # escola inteira + turmas
    assert _publish(client, s.direcao, title="").status_code == 422
    assert _publish(client, s.direcao, audience="todos").status_code == 422
