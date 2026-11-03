"""Testes de mensagens privadas: regras de contato, privacidade, não lidas e tempo real."""
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from app.models.classroom import Enrollment
from app.models.user import User
from tests.conftest import build_school_scenario as _setup
from tests.conftest import create_school, register_and_login


def _auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _contact_ids(client, token: str, q: str | None = None) -> set[str]:
    response = client.get("/api/v1/messages/contacts", headers=_auth(token), params={"q": q} if q else None)
    assert response.status_code == 200, response.text
    return {c["id"] for c in response.json()}


def _open(client, token: str, recipient_id: str):
    return client.post("/api/v1/messages/conversations", json={"recipient_id": recipient_id}, headers=_auth(token))


def _conversation_id(client, token: str, recipient_id: str) -> str:
    response = _open(client, token, recipient_id)
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def _send(client, token: str, conversation_id: str, body: str = "Olá!"):
    return client.post(
        f"/api/v1/messages/conversations/{conversation_id}/messages", json={"body": body}, headers=_auth(token)
    )


def _messages(client, token: str, conversation_id: str, **params):
    return client.get(
        f"/api/v1/messages/conversations/{conversation_id}/messages", headers=_auth(token), params=params
    )


def _conversations(client, token: str) -> list[dict]:
    response = client.get("/api/v1/messages/conversations", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def _mark_read(client, token: str, conversation_id: str):
    return client.post(f"/api/v1/messages/conversations/{conversation_id}/read", headers=_auth(token))


def _utc(iso: str) -> str:
    # O SQLite dos testes devolve datas sem fuso; o parâmetro `before` exige fuso.
    return iso if iso.endswith("Z") or "+" in iso else iso + "Z"


def test_management_can_contact_all_staff_and_guardians(client):
    s = _setup(client)
    expected = {s.secretaria_id, s.coordenacao_id, s.prof_a_id, s.prof_b_id, s.resp_a_id, s.resp_b_id, s.resp_livre_id}
    assert _contact_ids(client, s.direcao) == expected


def test_teacher_contacts_staff_and_guardians_of_own_students_only(client):
    s = _setup(client)
    assert _contact_ids(client, s.prof_a) == {s.direcao_id, s.secretaria_id, s.coordenacao_id, s.prof_b_id, s.resp_a_id}


def test_guardian_contacts_management_and_childs_teachers_only(client):
    s = _setup(client)
    assert _contact_ids(client, s.resp_a) == {s.direcao_id, s.secretaria_id, s.coordenacao_id, s.prof_a_id}
    assert _contact_ids(client, s.resp_livre) == {s.direcao_id, s.secretaria_id, s.coordenacao_id}


def test_contact_search_filters_by_name_and_escapes_wildcards(client):
    s = _setup(client)
    assert _contact_ids(client, s.direcao, q="coordenacao") == {s.coordenacao_id}
    assert _contact_ids(client, s.direcao, q="%") == set()
    # "_" é buscado literalmente: só o nome com sublinhado casa (sem escape, casaria com todos).
    assert _contact_ids(client, s.direcao, q="_") == {s.coordenacao_id}


def test_students_and_admin_have_no_access_to_messages(client):
    s = _setup(client)
    for token in (s.aluno, s.admin):
        assert client.get("/api/v1/messages/contacts", headers=_auth(token)).status_code == 403
        assert client.get("/api/v1/messages/conversations", headers=_auth(token)).status_code == 403
    assert client.get("/api/v1/messages/contacts").status_code == 401


def test_opening_a_conversation_is_idempotent_and_symmetric(client):
    s = _setup(client)
    first = _open(client, s.resp_a, s.prof_a_id)
    assert first.status_code == 201
    assert first.json()["other_user"]["id"] == s.prof_a_id
    assert first.json()["last_message"] is None
    assert first.json()["unread_count"] == 0

    again = _open(client, s.resp_a, s.prof_a_id)
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]

    from_teacher = _open(client, s.prof_a, s.resp_a_id)
    assert from_teacher.status_code == 200
    assert from_teacher.json()["id"] == first.json()["id"]
    assert from_teacher.json()["other_user"]["id"] == s.resp_a_id


def test_cannot_open_conversation_with_forbidden_or_unknown_users(client):
    s = _setup(client)
    assert _open(client, s.resp_a, s.resp_b_id).status_code == 403  # responsável não fala com responsável
    assert _open(client, s.resp_a, s.prof_b_id).status_code == 403  # professor de outra turma
    assert _open(client, s.prof_a, s.resp_b_id).status_code == 403  # responsável de outra turma
    assert _open(client, s.resp_a, s.aluno_id).status_code == 403  # aluno não usa mensagens
    assert _open(client, s.resp_a, s.resp_a_id).status_code == 404  # consigo mesmo
    assert _open(client, s.resp_a, str(uuid.uuid4())).status_code == 404


def test_conversations_are_isolated_between_schools(client):
    s = _setup(client)
    school_b = create_school(client, s.admin, name="Escola B", slug="escola-b")
    direcao_b = register_and_login(client, "direcao-b@escola.com", "direcao", school_id=school_b["id"])

    assert _open(client, direcao_b, s.direcao_id).status_code == 404
    assert _open(client, s.direcao, s.resp_a_id).status_code == 201
    assert _contact_ids(client, direcao_b) == set()


def test_send_message_tracks_unread_and_read_indicators(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)

    sent = _send(client, s.resp_a, conversation_id, "Bom dia, professora!")
    assert sent.status_code == 201
    body = sent.json()
    assert body["body"] == "Bom dia, professora!"
    assert body["sender_id"] == s.resp_a_id
    assert body["read_by_recipient"] is False

    teacher_view = _conversations(client, s.prof_a)
    assert len(teacher_view) == 1
    assert teacher_view[0]["unread_count"] == 1
    assert teacher_view[0]["other_user"]["id"] == s.resp_a_id
    assert teacher_view[0]["last_message"]["body"] == "Bom dia, professora!"
    assert _conversations(client, s.resp_a)[0]["unread_count"] == 0  # quem escreve já leu

    # Só abrir o histórico não marca como lida; é preciso chamar /read.
    assert _messages(client, s.prof_a, conversation_id).json()[0]["read_by_recipient"] is False
    assert _mark_read(client, s.prof_a, conversation_id).status_code == 204
    assert _conversations(client, s.prof_a)[0]["unread_count"] == 0
    assert _messages(client, s.resp_a, conversation_id).json()[0]["read_by_recipient"] is True

    assert _send(client, s.prof_a, conversation_id, "Bom dia!").status_code == 201
    assert _conversations(client, s.resp_a)[0]["unread_count"] == 1


def test_message_history_is_paginated_in_chronological_order(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)
    for number in range(1, 6):
        assert _send(client, s.resp_a, conversation_id, f"mensagem {number}").status_code == 201

    last_page = _messages(client, s.prof_a, conversation_id, limit=2).json()
    assert [m["body"] for m in last_page] == ["mensagem 4", "mensagem 5"]

    previous_page = _messages(client, s.prof_a, conversation_id, limit=2, before=_utc(last_page[0]["created_at"])).json()
    assert [m["body"] for m in previous_page] == ["mensagem 2", "mensagem 3"]

    everything = _messages(client, s.prof_a, conversation_id).json()
    assert [m["body"] for m in everything] == [f"mensagem {n}" for n in range(1, 6)]

    assert _messages(client, s.prof_a, conversation_id, limit=0).status_code == 422
    assert _messages(client, s.prof_a, conversation_id, before="2030-01-01T10:00:00").status_code == 422


def test_conversation_list_is_ordered_by_last_message_and_hides_empty_ones(client):
    s = _setup(client)
    with_teacher = _conversation_id(client, s.resp_a, s.prof_a_id)
    with_direcao = _conversation_id(client, s.resp_a, s.direcao_id)
    _conversation_id(client, s.resp_a, s.secretaria_id)  # aberta, mas sem mensagens

    _send(client, s.resp_a, with_direcao, "Para a direção")
    _send(client, s.resp_a, with_teacher, "Para a professora")

    assert [c["id"] for c in _conversations(client, s.resp_a)] == [with_teacher, with_direcao]
    _send(client, s.resp_a, with_direcao, "De novo para a direção")
    assert [c["id"] for c in _conversations(client, s.resp_a)] == [with_direcao, with_teacher]


def test_only_participants_can_access_a_conversation(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)
    _send(client, s.resp_a, conversation_id, "Assunto particular")

    # Nem a direção lê conversa alheia: só os dois participantes.
    for token in (s.prof_b, s.resp_b, s.direcao, s.coordenacao):
        assert _messages(client, token, conversation_id).status_code == 404
        assert _send(client, token, conversation_id, "intruso").status_code == 404
        assert _mark_read(client, token, conversation_id).status_code == 404
        assert _conversations(client, token) == []


def test_sending_is_blocked_when_contact_rule_no_longer_holds_but_history_stays(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)
    assert _send(client, s.resp_a, conversation_id, "Antes da troca de turma").status_code == 201

    # O filho deixa a turma da professora: ela deixa de ser contato do responsável.
    client.db_session.query(Enrollment).filter(Enrollment.classroom_id == uuid.UUID(s.class_a)).update(
        {"is_active": False}
    )
    client.db_session.commit()

    assert _send(client, s.resp_a, conversation_id, "Depois").status_code == 403
    assert _send(client, s.prof_a, conversation_id, "Depois").status_code == 403
    assert len(_messages(client, s.resp_a, conversation_id).json()) == 1
    assert len(_messages(client, s.prof_a, conversation_id).json()) == 1


def test_message_body_validation_and_trimming(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)

    assert _send(client, s.resp_a, conversation_id, "").status_code == 422
    assert _send(client, s.resp_a, conversation_id, "    ").status_code == 422
    assert _send(client, s.resp_a, conversation_id, "x" * 4001).status_code == 422
    assert _send(client, s.resp_a, conversation_id, "   Olá!   ").json()["body"] == "Olá!"


def test_message_events_are_sent_only_to_conversation_participants(client, monkeypatch):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)

    calls = []
    monkeypatch.setattr("app.api.routes_messages.notify_users", lambda ids, payload: calls.append((set(ids), payload)))

    _send(client, s.resp_a, conversation_id, "Oi")
    _mark_read(client, s.prof_a, conversation_id)

    assert [payload["type"] for _, payload in calls] == ["message", "read"]
    for recipients, _ in calls:
        assert recipients == {uuid.UUID(s.resp_a_id), uuid.UUID(s.prof_a_id)}


def _connect(client, ws, token: str):
    ws.send_json({"type": "auth", "token": token})
    assert ws.receive_json() == {"type": "ready"}


def test_websocket_delivers_message_and_read_events(client):
    s = _setup(client)
    conversation_id = _conversation_id(client, s.resp_a, s.prof_a_id)

    with client.websocket_connect("/ws/messages") as teacher_ws, client.websocket_connect("/ws/messages") as guardian_ws:
        _connect(client, teacher_ws, s.prof_a)
        _connect(client, guardian_ws, s.resp_a)

        _send(client, s.resp_a, conversation_id, "Oi, professora")
        for ws in (teacher_ws, guardian_ws):  # também chega ao autor (outras abas/dispositivos)
            event = ws.receive_json()
            assert event["type"] == "message"
            assert event["conversation_id"] == conversation_id
            assert event["message"]["body"] == "Oi, professora"
            assert event["message"]["sender_id"] == s.resp_a_id

        _mark_read(client, s.prof_a, conversation_id)
        for ws in (teacher_ws, guardian_ws):
            event = ws.receive_json()
            assert event["type"] == "read"
            assert event["conversation_id"] == conversation_id
            assert event["reader_id"] == s.prof_a_id


def test_websocket_answers_ping_and_cleans_up_connections(client):
    from app.services.realtime import manager

    s = _setup(client)
    with client.websocket_connect("/ws/messages") as ws:
        _connect(client, ws, s.resp_a)
        assert manager.is_connected(uuid.UUID(s.resp_a_id))
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
    assert not manager.is_connected(uuid.UUID(s.resp_a_id))


@pytest.mark.parametrize("first_message", [{"type": "auth", "token": "token-invalido"}, {"type": "auth"}, {"oi": 1}])
def test_websocket_rejects_invalid_authentication(client, first_message):
    with client.websocket_connect("/ws/messages") as ws:
        ws.send_json(first_message)
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
    assert error.value.code == 1008


def test_websocket_rejects_users_without_messaging_access_and_inactive_users(client):
    s = _setup(client)
    for token in (s.aluno, s.admin):
        with client.websocket_connect("/ws/messages") as ws:
            ws.send_json({"type": "auth", "token": token})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

    client.db_session.query(User).filter_by(id=uuid.UUID(s.resp_a_id)).update({"is_active": False})
    client.db_session.commit()
    with client.websocket_connect("/ws/messages") as ws:
        ws.send_json({"type": "auth", "token": s.resp_a})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_websocket_closes_when_authentication_takes_too_long(client, monkeypatch):
    monkeypatch.setattr("app.api.routes_messages.AUTH_TIMEOUT_SECONDS", 0.2)
    with client.websocket_connect("/ws/messages") as ws:
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
    assert error.value.code == 1008
