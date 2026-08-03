"""Puerto de notificaciones usado por cualquier módulo de dominio.

La implementación concreta (canales WebSocket, Web Push VAPID) vive en el
módulo `notificaciones` (transversal, sin CU formal — ver ítem A1 del plan) y
se registra en `app.state.notification_dispatcher` durante el startup de
`main.py`. Los módulos de dominio dependen solo de esta interfaz, nunca de la
implementación, para no crear un acoplamiento circular entre paquetes.
"""

from typing import Any, Protocol

from fastapi import Request


class NotificationDispatcher(Protocol):
    async def notify_user(self, usuario_id: str, event: str, payload: dict[str, Any]) -> None: ...

    async def broadcast_channel(self, channel: str, event: str, payload: dict[str, Any]) -> None: ...


class NoopNotificationDispatcher:
    """Fallback usado antes de que el módulo `notificaciones` registre la
    implementación real (p. ej. en tests unitarios de otros módulos)."""

    async def notify_user(self, usuario_id: str, event: str, payload: dict[str, Any]) -> None:
        return None

    async def broadcast_channel(self, channel: str, event: str, payload: dict[str, Any]) -> None:
        return None


def get_notification_dispatcher(request: Request) -> NotificationDispatcher:
    return getattr(request.app.state, "notification_dispatcher", NoopNotificationDispatcher())
