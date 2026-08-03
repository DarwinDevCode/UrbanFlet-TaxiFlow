from typing import Any

from src.core.db_mongo import get_database
from src.notificaciones.connection_manager import connection_manager
from src.notificaciones.webpush import send_web_push


def user_channel(usuario_id: str) -> str:
    return f"user:{usuario_id}"


def trip_passenger_channel(viaje_id: str) -> str:
    return f"viaje:{viaje_id}"


TABLERO_FLOTA_CHANNEL = "tablero-flota"


class NotificationService:
    """Implementación concreta de `core.notifications.NotificationDispatcher`,
    registrada en `app.state.notification_dispatcher` durante el startup."""

    async def notify_user(self, usuario_id: str, event: str, payload: dict[str, Any]) -> None:
        channel = user_channel(usuario_id)
        if connection_manager.has_connections(channel):
            await connection_manager.send_to_channel(channel, event, payload)
            return

        # Sin conexión WS activa (pestaña cerrada / segundo plano): se
        # entrega por Web Push, como exige la arquitectura.
        db = get_database()
        async for sub in db.push_subscriptions.find({"usuario_id": usuario_id}):
            await send_web_push(sub["subscription_info"], {"event": event, "payload": payload})

    async def broadcast_channel(self, channel: str, event: str, payload: dict[str, Any]) -> None:
        await connection_manager.send_to_channel(channel, event, payload)
