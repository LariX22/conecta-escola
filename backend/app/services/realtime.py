"""Entrega de eventos em tempo real por WebSocket (conexões mantidas em memória).

Limitação conhecida: as conexões ficam na memória deste processo. Com mais de
uma instância da API será preciso um canal compartilhado (Redis pub/sub, já
previsto na arquitetura) para o evento chegar à instância onde o usuário está
conectado. Com uma única instância (caso atual) funciona sem isso.
"""
import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import anyio.from_thread
from fastapi import WebSocket

logger = logging.getLogger(__name__)

SEND_TIMEOUT_SECONDS = 5


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self._connections[user_id]

    def is_connected(self, user_id: uuid.UUID) -> bool:
        return bool(self._connections.get(user_id))

    async def send_to_users(self, user_ids: Iterable[uuid.UUID], payload: dict[str, Any]) -> None:
        for user_id in set(user_ids):
            for websocket in list(self._connections.get(user_id, ())):
                try:
                    await asyncio.wait_for(websocket.send_json(payload), timeout=SEND_TIMEOUT_SECONDS)
                except Exception:
                    logger.warning("Conexão em tempo real descartada após falha de envio.")
                    self.disconnect(user_id, websocket)


manager = ConnectionManager()
_background_tasks: set[asyncio.Task] = set()


def _schedule_delivery(user_ids: list[uuid.UUID], payload: dict[str, Any]) -> None:
    task = asyncio.get_running_loop().create_task(manager.send_to_users(user_ids, payload))
    _background_tasks.add(task)  # referência forte até terminar
    task.add_done_callback(_background_tasks.discard)


def notify_users(user_ids: Iterable[uuid.UUID], payload: dict[str, Any]) -> None:
    """Agenda o envio do evento sem esperar a entrega (chamado de rotas síncronas).

    Falhas aqui nunca derrubam a requisição REST: a mensagem já foi gravada e
    o cliente a recebe na próxima consulta.
    """
    try:
        anyio.from_thread.run_sync(_schedule_delivery, list(user_ids), payload)
    except Exception:
        logger.exception("Falha ao agendar o evento em tempo real.")
