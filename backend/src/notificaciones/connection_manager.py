"""Gestor de conexiones WebSocket en memoria de proceso.

El backend corre como "un servicio por componente" (un solo proceso FastAPI,
ver docker-compose.yml), así que un registro en memoria es suficiente para
Fase 0. Si en el futuro el backend se replica horizontalmente, este gestor
debe respaldarse en Redis Pub/Sub — se deja como nota, no como código muerto.
"""

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._channels[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        self._channels[channel].discard(websocket)
        if not self._channels[channel]:
            self._channels.pop(channel, None)

    async def send_to_channel(self, channel: str, event: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"event": event, "payload": payload})
        dead: list[WebSocket] = []
        for ws in self._channels.get(channel, set()):
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001 — socket puede fallar de formas específicas del transporte; cualquier fallo lo marca como muerto.
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)

    def has_connections(self, channel: str) -> bool:
        return bool(self._channels.get(channel))


connection_manager = ConnectionManager()
