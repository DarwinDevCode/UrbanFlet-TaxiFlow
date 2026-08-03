"""Canales en tiempo real (arquitectura_software.md §4.2, línea 91-99):
- /ws/pasajero/{viaje_id}: posición del conductor, transiciones, ETA, chat
- /ws/conductor: ofertas de viaje, transiciones, chat
- /ws/tablero-flota: posiciones y alertas de toda la flota (solo Coordinador de Flota)

Los navegadores no permiten fijar headers en el handshake WS, así que la
autenticación viaja como query param `token` (mismo JWT que el resto de la API).
"""

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor
from src.core.security import TokenType, decode_token
from src.notificaciones.connection_manager import connection_manager
from src.notificaciones.service import TABLERO_FLOTA_CHANNEL, trip_passenger_channel, user_channel

router = APIRouter(tags=["notificaciones"])


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
