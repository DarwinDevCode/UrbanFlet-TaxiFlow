from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.notificaciones.service import trip_passenger_channel
from src.viajes import schemas, service_ejecucion
from src.viajes.router_trips import to_out

router = APIRouter(prefix="/viajes/conductor", tags=["viajes"])

_conductor = require_roles("conductor")


async def _notificar_pasajero(dispatcher: NotificationDispatcher, viaje: dict, evento_bandeja: str) -> None:
    # Mismo patrón que la notificación de asignación (Slice 3): un evento
    # genérico basta porque el cliente siempre refresca desde
    # GET /viajes/activo — una única fuente de verdad, sin duplicar el mapeo
    # de campos por tipo de evento en el WebSocket.
    await dispatcher.broadcast_channel(trip_passenger_channel(viaje["_id"]), "VIAJE_ACTUALIZADO", {})
    # Además del evento efímero de arriba, se registra en la bandeja de
    # notificaciones in-app del pasajero (Sección 4.2 de
    # ux_complementaria.md) -- con un tipo distinto por transición, para que
    # la bandeja sea legible ("Conductor en camino" vs. "Viaje finalizado").
    await dispatcher.notify_user(viaje["pasajero_id"], evento_bandeja, {"viaje_id": viaje["_id"]})


@router.post("/en-camino", response_model=schemas.ViajeOut)
async def marcar_en_camino(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_ejecucion.marcar_en_camino(db, conductor_id=actor.usuario_id)
    await _notificar_pasajero(dispatcher, viaje, "CONDUCTOR_EN_CAMINO")
    return to_out(viaje)


@router.post("/llegue", response_model=schemas.ViajeOut)
async def marcar_llegada(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_ejecucion.marcar_llegada(db, conductor_id=actor.usuario_id)
    await _notificar_pasajero(dispatcher, viaje, "CONDUCTOR_LLEGO")
    return to_out(viaje)


@router.post("/iniciar", response_model=schemas.ViajeOut)
async def iniciar_viaje(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_ejecucion.iniciar_viaje(db, conductor_id=actor.usuario_id)
    await _notificar_pasajero(dispatcher, viaje, "VIAJE_INICIADO")
    return to_out(viaje)


class CancelarConductorRequest(BaseModel):
    motivo: str


@router.post("/cancelar", response_model=schemas.ViajeOut)
async def cancelar_por_conductor(
    body: CancelarConductorRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_ejecucion.cancelar_por_conductor(db, conductor_id=actor.usuario_id, motivo=body.motivo)
    await _notificar_pasajero(dispatcher, viaje, "VIAJE_CANCELADO_CONDUCTOR")
    return to_out(viaje)


@router.post("/recalculo-ruta", status_code=status.HTTP_204_NO_CONTENT)
async def registrar_recalculo_ruta(
    body: schemas.RecalculoRutaRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    # CU-O07 A6: el cliente ya recalculó la ruta (GET /viajes/estimacion-ruta)
    # al detectar un desvío >2km -- este endpoint solo deja el registro que la
    # spec exige en la bitácora (CU-O17). Sin efecto de negocio propio, sin
    # response body.
    await service_ejecucion.registrar_recalculo_ruta_por_desvio(
        db,
        conductor_id=actor.usuario_id,
        lat=body.lat,
        lon=body.lon,
        distancia_desvio_km=body.distancia_desvio_km,
        ruta_anterior=body.ruta_anterior,
        ruta_nueva=body.ruta_nueva,
    )
