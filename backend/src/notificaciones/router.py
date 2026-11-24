"""Canales en tiempo real (arquitectura_software.md §4.2, línea 91-99):
- /ws/pasajero/{viaje_id}: posición del conductor, transiciones, ETA, chat
- /ws/conductor: ofertas de viaje, transiciones, chat
- /ws/tablero-flota: posiciones y alertas de toda la flota (solo Coordinador de Flota)

Los navegadores no permiten fijar headers en el handshake WS, así que la
autenticación viaja como query param `token` (mismo JWT que el resto de la API).
"""

from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor, require_roles
from src.core.security import TokenType, decode_token
from src.notificaciones import schemas as alertas_schemas
from src.notificaciones import service
from src.notificaciones.connection_manager import connection_manager
from src.notificaciones.service import TABLERO_FLOTA_CHANNEL, trip_passenger_channel, user_channel

router = APIRouter(tags=["notificaciones"])

# Módulo 6.3 de admin_sistema -- alto privilegio, exclusivo admin_sistema.
_admin_sistema = require_roles("admin_sistema")


async def _actor_from_ws_token(token: str, db: AsyncIOMotorDatabase) -> Actor | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != TokenType.ACCESS.value:
            return None
    except jwt.PyJWTError:
        return None

    usuario = await db.usuarios.find_one({"_id": payload["sub"]})
    if usuario is None or usuario.get("estado") != "ACTIVO":
        return None
    return Actor(usuario_id=usuario["_id"], roles=usuario.get("roles", []), estado=usuario["estado"])


@router.websocket("/ws/pasajero/{viaje_id}")
async def ws_pasajero(websocket: WebSocket, viaje_id: str, token: str):
    db = get_database()
    actor = await _actor_from_ws_token(token, db)
    if actor is None or "pasajero" not in actor.roles:
        await websocket.close(code=4401)
        return

    # Diferido desde Fase 0 hasta que existiera `viajes` (Fase 3): confirma
    # que el viaje pertenece a quien pide conectarse, para que un pasajero no
    # pueda suscribirse al canal de otro adivinando su viaje_id.
    viaje = await db.viajes.find_one({"_id": viaje_id})
    if viaje is None or viaje["pasajero_id"] != actor.usuario_id:
        await websocket.close(code=4403)
        return

    channel = trip_passenger_channel(viaje_id)
    await connection_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()  # chat entrante del pasajero
    except WebSocketDisconnect:
        connection_manager.disconnect(channel, websocket)


@router.websocket("/ws/conductor")
async def ws_conductor(websocket: WebSocket, token: str):
    db = get_database()
    actor = await _actor_from_ws_token(token, db)
    if actor is None or "conductor" not in actor.roles:
        await websocket.close(code=4401)
        return

    channel = user_channel(actor.usuario_id)
    await connection_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()  # respuesta a oferta / chat
    except WebSocketDisconnect:
        connection_manager.disconnect(channel, websocket)


@router.websocket("/ws/tablero-flota")
async def ws_tablero_flota(websocket: WebSocket, token: str):
    db = get_database()
    actor = await _actor_from_ws_token(token, db)
    if actor is None or not actor.has_any_role({"coordinador_flota", "admin_plataforma"}):
        await websocket.close(code=4403)
        return

    await connection_manager.connect(TABLERO_FLOTA_CHANNEL, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(TABLERO_FLOTA_CHANNEL, websocket)


class PushSubscribeRequest(BaseModel):
    subscription_info: dict


@router.post("/notificaciones/push/subscribe", status_code=201)
async def suscribir_push(
    body: PushSubscribeRequest,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    endpoint = body.subscription_info.get("endpoint")
    await db.push_subscriptions.update_one(
        {"usuario_id": actor.usuario_id, "subscription_info.endpoint": endpoint},
        {"$set": {"usuario_id": actor.usuario_id, "subscription_info": body.subscription_info}},
        upsert=True,
    )
    return {"estado": "SUSCRITO"}


@router.get("/notificaciones/alertas-config", response_model=list[alertas_schemas.ConfiguracionAlertaOut])
async def listar_alertas_config(
    actor: Actor = Depends(_admin_sistema), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await service.listar_configuraciones_alerta(db)


@router.patch("/notificaciones/alertas-config/{tipo_alerta}", response_model=alertas_schemas.ConfiguracionAlertaOut)
async def actualizar_alerta_config(
    tipo_alerta: alertas_schemas.TipoAlerta,
    body: alertas_schemas.ConfiguracionAlertaActualizar,
    actor: Actor = Depends(_admin_sistema),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await service.actualizar_configuracion_alerta(
        db,
        actor_id=actor.usuario_id,
        rol=",".join(actor.roles),
        tipo_alerta=tipo_alerta,
        canal=body.canal,
        destinatarios_adicionales=body.destinatarios_adicionales,
        activo=body.activo,
    )


def _notificacion_to_out(doc: dict) -> alertas_schemas.NotificacionOut:
    return alertas_schemas.NotificacionOut(
        id=doc["_id"], tipo=doc["tipo"], categoria=doc["categoria"], payload=doc["payload"],
        ts=doc["ts"], leida=doc["leida"],
    )


@router.get("/notificaciones/mias", response_model=alertas_schemas.NotificacionListOut)
async def listar_mias(
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
    tipo: str | None = Query(default=None),
    leida: bool | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total, no_leidas = await service.listar_notificaciones(
        db,
        usuario_id=actor.usuario_id,
        pagina=pagina,
        limite=limite,
        tipo=tipo,
        leida=leida,
        desde=desde,
        hasta=hasta,
    )
    return alertas_schemas.NotificacionListOut(
        items=[_notificacion_to_out(d) for d in items], total=total, no_leidas=no_leidas
    )


@router.patch("/notificaciones/mias/{notificacion_id}/leida", response_model=alertas_schemas.NotificacionOut)
async def marcar_leida(
    notificacion_id: str,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.marcar_leida(db, usuario_id=actor.usuario_id, notificacion_id=notificacion_id)
    return _notificacion_to_out(doc)


@router.get("/notificaciones/categorias", response_model=list[alertas_schemas.CategoriaNotificacionOut])
async def listar_categorias(actor: Actor = Depends(get_current_actor)):
    return [alertas_schemas.CategoriaNotificacionOut(**c) for c in service.CATEGORIAS_CONFIGURABLES]
