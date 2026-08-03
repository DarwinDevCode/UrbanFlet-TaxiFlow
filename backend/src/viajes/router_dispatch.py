from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.notificaciones.service import trip_passenger_channel
from src.viajes import schemas, service_dispatch

router = APIRouter(prefix="/viajes", tags=["viajes"])

_conductor = require_roles("conductor")


@router.get("/oferta-actual", response_model=schemas.OfertaActualOut)
async def obtener_oferta_actual(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service_dispatch.obtener_oferta_actual(db, conductor_id=actor.usuario_id)
    if resultado is None:
        raise service_dispatch.SinOfertaActivaError()
    viaje, _oferta = resultado
    return await service_dispatch.construir_oferta_out(db, viaje, actor.usuario_id)


@router.post("/oferta/responder")
async def responder_oferta(
    body: schemas.ResponderOfertaRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_dispatch.responder_oferta(db, conductor_id=actor.usuario_id, aceptar=body.aceptar)
    if viaje["estado"] == "ASIGNADO":
        # El pasajero escucha en el canal del VIAJE (/ws/pasajero/{viaje_id}),
        # no en su canal de usuario — notify_user() manda al canal de usuario
        # y nadie estaría escuchando ahí para esto. broadcast_channel() con
        # el canal correcto es la forma correcta de empujar un evento
        # específico de un viaje. Evento genérico + refetch del cliente desde
        # GET /viajes/activo (mismo patrón que las transiciones de CU-O07,
        # Slice 4) en vez de mandar los campos y duplicar el mapeo en el
        # front. (Sin fallback de Web Push aquí: a diferencia de
        # notify_user(), este evento es efímero — si el pasajero no está
        # conectado, el próximo poll de GET /viajes/activo ya refleja
        # ASIGNADO de todas formas.)
        await dispatcher.broadcast_channel(trip_passenger_channel(viaje["_id"]), "VIAJE_ACTUALIZADO", {})
    return {"estado": viaje["estado"]}
