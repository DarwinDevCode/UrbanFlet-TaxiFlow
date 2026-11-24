import uuid
from datetime import datetime, UTC
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.exceptions import DomainError
from src.notificaciones.connection_manager import connection_manager
from src.notificaciones.webpush import send_web_push


def user_channel(usuario_id: str) -> str:
    return f"user:{usuario_id}"


def trip_passenger_channel(viaje_id: str) -> str:
    return f"viaje:{viaje_id}"


TABLERO_FLOTA_CHANNEL = "tablero-flota"

# ---------------------------------------------------------------------------
# Módulo 6.3 de admin_sistema (specs/specs-administrativas/admin_sistema.md):
# "administrar a quién y cómo llegan las alertas que el sistema ya genera
# (spoofing GPS, cinco denegaciones consecutivas, corrida de pipeline
# fallida) — hoy fijas a destinatarios específicos en código."
#
# Investigación previa a construir esto (confirmada por lectura de código,
# no asumida): de las 3, solo "cinco denegaciones" estaba realmente
# conectada a un envío (`core/rbac.py`, a `supervisor_cumplimiento`
# hardcodeado). "Spoofing GPS" solo escribía un evento de auditoría --
# nunca notificaba a nadie, pese a que la spec la lista como una alerta que
# "el sistema ya genera". Se corrigió: `flota/service.py` ahora dispara una
# notificación real, no solo la spec lo dio por hecho.
# "Pipeline fallido" es enteramente del lado de Airflow (ver
# `analytics/plugins/medallion.py::registrar_alerta_falla`) -- no existe
# ningún webhook Airflow→backend hoy, así que este tipo queda configurable
# (canal/destinatarios/activo, visible en el catálogo) pero SIN disparo real
# desde este backend -- documentado explícitamente, no simulado.
# ---------------------------------------------------------------------------

TIPOS_ALERTA: tuple[str, ...] = (
    "denegaciones_rbac",
    "gps_spoofing",
    "pipeline_fallido",
    "reporte_falla",
    "incidencia_operativa",
)

# Rol que recibe la alerta por defecto (además de los destinatarios
# adicionales configurados) -- el mismo destinatario que ya estaba
# hardcodeado en el código antes de este módulo, para no cambiar
# comportamiento hasta que un admin_sistema lo reconfigure explícitamente.
# "reporte_falla" (Ronda 2 del flujo de fallas, Fase C) es la excepción: no
# reemplaza ningún envío hardcodeado previo -- antes de esta ronda, un
# reporte de falla del conductor simplemente no notificaba a nadie.
# "incidencia_operativa" (misma Fase C, corrección posterior): CU-O07 A4
# pide un aviso EN VIVO al Coordinador de Operaciones cuando el conductor
# registra la incidencia -- distinto propósito del de "reporte_falla"
# (que alimenta la bandeja de pre-órdenes del Jefe de Mantenimiento, Fase
# D), así que es un tipo de alerta propio y no una reutilización, siguiendo
# el mismo criterio "un tipo de alerta = un rol destinatario" ya establecido
# acá para el resto del catálogo. `reportes_falla/service.py::
# crear_reporte_falla` dispara los DOS tipos en el mismo evento, sin que
# uno dependa del otro.
ROL_DEFAULT_POR_ALERTA: dict[str, str] = {
    "denegaciones_rbac": "supervisor_cumplimiento",
    "gps_spoofing": "supervisor_cumplimiento",
    "pipeline_fallido": "responsable_plataforma",
    "reporte_falla": "jefe_mantenimiento",
    "incidencia_operativa": "coordinador_operaciones",
}

DEFAULTS_ALERTA = {"canal": "web_push", "destinatarios_adicionales": [], "activo": True}


# Sección 4.2 de ux_complementaria.md: taxonomía de tipos de notificación
# por categoría -- usada tanto para persistir cada notificación con su
# categoría (bandeja in-app) como para el filtro de push por categoría de
# la Sección 1.4 (`preferencias.notificaciones_push`). "seguridad" es la
# única categoría que NUNCA se apaga desde acá (nota de la spec 1.4: las
# notificaciones de seguridad son exclusivas del Módulo 6.3).
CATEGORIA_POR_EVENTO: dict[str, str] = {
    "NUEVA_SOLICITUD": "captacion",
    "SOLICITUD_DECISION": "captacion",
    "RENOVACION_DOCUMENTO_DECISION": "cumplimiento",
    # Hallazgo real de la ronda del Centro de notificaciones (sección completa):
    # estos 2 tipos ya se disparaban desde `cumplimiento/service.py` pero
    # nunca se habían agregado acá -- caían en el fallback "general" (sin
    # categoría configurable de push, aunque siempre entregados). Corregido
    # para que compartan categoría con RENOVACION_DOCUMENTO_DECISION, el
    # mismo dominio.
    "DOCUMENTO_VENCIDO": "cumplimiento",
    "DOCUMENTO_POR_VENCER": "cumplimiento",
    "ORDEN_MANTENIMIENTO_REGISTRADA": "mantenimiento",
    "ORDEN_MANTENIMIENTO_CERRADA": "mantenimiento",
    "ALERTA_SEGURIDAD": "seguridad",
    "VIAJE_ASIGNADO": "viaje",
    "CONDUCTOR_EN_CAMINO": "viaje",
    "CONDUCTOR_LLEGO": "viaje",
    "VIAJE_INICIADO": "viaje",
    "VIAJE_FINALIZADO": "viaje",
    "VIAJE_CANCELADO_CONDUCTOR": "viaje",
}

CATEGORIAS_CONFIGURABLES = [
    {"valor": "captacion", "etiqueta": "Postulaciones y solicitudes"},
    {"valor": "cumplimiento", "etiqueta": "Documentos y renovaciones"},
    {"valor": "mantenimiento", "etiqueta": "Órdenes de mantenimiento"},
    {"valor": "viaje", "etiqueta": "Estado del viaje"},
]


def _categoria(event: str) -> str:
    return CATEGORIA_POR_EVENTO.get(event, "general")


async def _persistir_notificacion(db: AsyncIOMotorDatabase, usuario_id: str, event: str, payload: dict) -> None:
    # Best-effort: la bandeja in-app es una red de seguridad, nunca debe
    # bloquear ni reventar el envío en vivo (mismo criterio que
    # `_registrar_historial` en `sistema/service.py`).
    try:
        await db.notificaciones_usuario.insert_one({
            "_id": str(uuid.uuid4()),
            "usuario_id": usuario_id,
            "tipo": event,
            "categoria": _categoria(event),
            "payload": payload,
            "ts": datetime.now(UTC),
            "leida": False,
        })
    except Exception:  # noqa: BLE001
        pass


async def _push_habilitado(db: AsyncIOMotorDatabase, usuario_id: str, event: str) -> bool:
    categoria = _categoria(event)
    if categoria == "seguridad":
        return True
    doc = await db.preferencias_usuario.find_one({"_id": usuario_id})
    preferencias = (doc or {}).get("notificaciones_push", {})
    return preferencias.get(categoria, True)


class NotificationService:
    """Implementación concreta de `core.notifications.NotificationDispatcher`,
    registrada en `app.state.notification_dispatcher` durante el startup."""

    async def notify_user(self, usuario_id: str, event: str, payload: dict[str, Any]) -> None:
        db = get_database()
        # Persistencia in-app SIEMPRE, sin importar el canal de entrega en
        # vivo ni la preferencia de push -- apagar el push no debe vaciar la
        # bandeja (Sección 4.2/1.4 del plan).
        await _persistir_notificacion(db, usuario_id, event, payload)

        channel = user_channel(usuario_id)
        if connection_manager.has_connections(channel):
            await connection_manager.send_to_channel(channel, event, payload)
            return

        if not await _push_habilitado(db, usuario_id, event):
            return

        # Sin conexión WS activa (pestaña cerrada / segundo plano): se
        # entrega por Web Push, como exige la arquitectura.
        async for sub in db.push_subscriptions.find({"usuario_id": usuario_id}):
            await send_web_push(sub["subscription_info"], {"event": event, "payload": payload})

    async def broadcast_channel(self, channel: str, event: str, payload: dict[str, Any]) -> None:
        await connection_manager.send_to_channel(channel, event, payload)


async def listar_notificaciones(
    db: AsyncIOMotorDatabase,
    *,
    usuario_id: str,
    pagina: int = 1,
    limite: int = 20,
    tipo: str | None = None,
    leida: bool | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> tuple[list[dict], int, int]:
    """Sección completa del Centro de notificaciones: filtros por tipo,
    estado y rango de fecha, todos opcionales y combinables (mismo patrón
    de filtros server-side que el resto de pantallas WorkPanel/bitácora).

    `no_leidas` se calcula SIEMPRE sobre `{usuario_id}` sin ningún filtro
    -- es el contador global que la campana y el ítem del sidebar muestran;
    filtrar la lista visible (ej. por tipo) no debe hacer que ese número
    "baje" de forma engañosa mientras siguen existiendo notificaciones sin
    leer fuera del filtro actual.
    """
    base = {"usuario_id": usuario_id}
    filtro: dict = dict(base)
    if tipo:
        filtro["tipo"] = tipo
    if leida is not None:
        filtro["leida"] = leida
    if desde or hasta:
        rango: dict = {}
        if desde:
            rango["$gte"] = desde
        if hasta:
            rango["$lte"] = hasta
        filtro["ts"] = rango

    total = await db.notificaciones_usuario.count_documents(filtro)
    no_leidas = await db.notificaciones_usuario.count_documents({**base, "leida": False})
    cursor = (
        db.notificaciones_usuario.find(filtro)
        .sort("ts", -1)
        .skip((pagina - 1) * limite)
        .limit(limite)
    )
    items = await cursor.to_list(length=limite)
    return items, total, no_leidas


class NotificacionNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="NOTIFICACION_NO_ENCONTRADA", message="La notificación no existe", status_code=404)


async def marcar_leida(db: AsyncIOMotorDatabase, *, usuario_id: str, notificacion_id: str) -> dict:
    doc = await db.notificaciones_usuario.find_one({"_id": notificacion_id, "usuario_id": usuario_id})
    if doc is None:
        raise NotificacionNoEncontradaError()
    if not doc["leida"]:
        await db.notificaciones_usuario.update_one({"_id": notificacion_id}, {"$set": {"leida": True}})
        doc["leida"] = True
    return doc


async def obtener_configuracion_alerta(db: AsyncIOMotorDatabase, tipo_alerta: str) -> dict:
    """Nunca lanza -- sin configuración publicada cae a `DEFAULTS_ALERTA`
    (el comportamiento que ya regía antes de este módulo: activa, sin
    destinatarios adicionales, único canal real)."""
    doc = await db.configuracion_alertas.find_one({"_id": tipo_alerta})
    if doc is None:
        return dict(DEFAULTS_ALERTA)
    return {
        "canal": doc["canal"],
        "destinatarios_adicionales": doc["destinatarios_adicionales"],
        "activo": doc["activo"],
    }


async def listar_configuraciones_alerta(db: AsyncIOMotorDatabase) -> list[dict]:
    salida = []
    for tipo_alerta in TIPOS_ALERTA:
        doc = await db.configuracion_alertas.find_one({"_id": tipo_alerta})
        config = await obtener_configuracion_alerta(db, tipo_alerta)
        salida.append({
            "tipo_alerta": tipo_alerta,
            "rol_destinatario_default": ROL_DEFAULT_POR_ALERTA[tipo_alerta],
            "actualizado_en": doc.get("actualizado_en") if doc else None,
            **config,
        })
    return salida


async def actualizar_configuracion_alerta(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    tipo_alerta: str,
    canal: str,
    destinatarios_adicionales: list[str],
    activo: bool,
) -> dict:
    from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event

    if tipo_alerta not in TIPOS_ALERTA:
        raise ValueError(f"tipo_alerta desconocido: {tipo_alerta}")

    anterior = await obtener_configuracion_alerta(db, tipo_alerta)
    nuevo = {"canal": canal, "destinatarios_adicionales": destinatarios_adicionales, "activo": activo}

    # Write-ahead con antes/después -- la nota de seguridad de la spec exige
    # que desactivar una alerta de seguridad quede trazado, no que sea
    # imposible; este evento es esa traza.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.ALERTA_CONFIG_CAMBIO,
        entidad="configuracion_alertas",
        entidad_id=tipo_alerta,
        resultado=ResultadoAuditoria.OK,
        datos_previos=anterior,
        datos_posteriores=nuevo,
    )

    ahora = datetime.now(UTC)
    await db.configuracion_alertas.update_one(
        {"_id": tipo_alerta}, {"$set": {**nuevo, "actualizado_en": ahora}}, upsert=True
    )
    doc = await db.configuracion_alertas.find_one({"_id": tipo_alerta})
    return {
        "tipo_alerta": tipo_alerta,
        "rol_destinatario_default": ROL_DEFAULT_POR_ALERTA[tipo_alerta],
        "actualizado_en": doc["actualizado_en"],
        "canal": doc["canal"],
        "destinatarios_adicionales": doc["destinatarios_adicionales"],
        "activo": doc["activo"],
    }


async def disparar_alerta(db: AsyncIOMotorDatabase, dispatcher: Any, *, tipo_alerta: str, motivo: str) -> None:
    """Punto único de disparo para las alertas configurables de Módulo 6.3
    -- reemplaza el envío hardcodeado que antes vivía separado en cada
    módulo de dominio (`core/rbac.py`, y ahora también `flota/service.py`).
    `dispatcher` es `request.app.state.notification_dispatcher` -- puede
    ser `None` en contextos sin lifespan (algunos tests), en cuyo caso no
    hace nada, igual que ya toleraba `core/rbac.py` antes de este cambio."""
    if dispatcher is None:
        return

    config = await obtener_configuracion_alerta(db, tipo_alerta)
    if not config["activo"]:
        return

    destinatarios = set(config["destinatarios_adicionales"])
    rol_default = ROL_DEFAULT_POR_ALERTA[tipo_alerta]
    async for usuario in db.usuarios.find({"roles": rol_default}):
        destinatarios.add(usuario["_id"])

    for usuario_id in destinatarios:
        await dispatcher.notify_user(usuario_id, "ALERTA_SEGURIDAD", {"tipo_alerta": tipo_alerta, "motivo": motivo})
