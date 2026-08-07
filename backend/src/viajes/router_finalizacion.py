from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.exceptions import DomainError
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, get_current_actor, require_roles
from src.notificaciones.service import trip_passenger_channel
from src.viajes import schemas, service_finalizacion, service_historial
from src.viajes.router_trips import to_out
from src.viajes.service import SinViajeActivoError

router = APIRouter(prefix="/viajes", tags=["viajes"])

_conductor = require_roles("conductor")


class RolNoValidoParaCalificarError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ROL_NO_VALIDO",
            message="Solo el pasajero o el conductor del viaje pueden calificarlo",
            status_code=403,
        )


@router.post("/conductor/finalizar", response_model=schemas.ViajeOut)
async def finalizar_viaje(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    viaje = await service_finalizacion.finalizar_viaje(db, conductor_id=actor.usuario_id)
    await dispatcher.broadcast_channel(trip_passenger_channel(viaje["_id"]), "VIAJE_ACTUALIZADO", {})
    # Bandeja de notificaciones in-app (Sección 4.2 de ux_complementaria.md).
    await dispatcher.notify_user(viaje["pasajero_id"], "VIAJE_FINALIZADO", {"viaje_id": viaje["_id"]})
    return to_out(viaje)


@router.post("/{viaje_id}/calificar", response_model=schemas.ViajeOut)
async def calificar_viaje(
    viaje_id: str,
    body: schemas.CalificarViajeRequest,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if "pasajero" in actor.roles:
        rol = "pasajero"
    elif "conductor" in actor.roles:
        rol = "conductor"
    else:
        raise RolNoValidoParaCalificarError()

    viaje = await service_finalizacion.calificar_viaje(
        db, viaje_id=viaje_id, actor_id=actor.usuario_id, rol=rol, puntaje=body.puntaje, comentario=body.comentario
    )
    return to_out(viaje)


# IMPORTANTE: registrada al final, en el router que main.py monta último —
# GET /viajes/{viaje_id} tiene la misma forma de path que rutas literales de
# OTROS routers de viajes (p. ej. GET /viajes/oferta-actual en
# router_dispatch.py). FastAPI/Starlette resuelve rutas en el orden en que
# se registran en la app completa, así que si esta ruta se montara antes,
# capturaría "oferta-actual" como si fuera un viaje_id y las rutas literales
# de los otros routers nunca se alcanzarían.
#
# Existe porque GET /viajes/activo (router_trips.py) solo devuelve viajes en
# un estado ACTIVO por diseño — una vez que un viaje llega a FINALIZADO deja
# de aparecer ahí, y un cliente que lo venía siguiendo (poll o WebSocket)
# nunca podría enterarse de esa transición, quedándose en un 404 permanente
# justo cuando más importa (CU-O08: mostrar tarifa final y calificación).
# Esta ruta, en cambio, siempre devuelve el viaje sin importar su estado —
# pensada para cuando el cliente YA conoce el id (lo tiene desde que lo creó
# o desde /activo) y solo necesita seguir su evolución hasta el cierre.
@router.get("/{viaje_id}", response_model=schemas.ViajeOut)
async def obtener_viaje_por_id(
    viaje_id: str,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viaje = await db.viajes.find_one({"_id": viaje_id})
    if viaje is None or (viaje["pasajero_id"] != actor.usuario_id and viaje.get("conductor_id") != actor.usuario_id):
        # Mismo código que "sin viaje" — no se distingue "no existe" de "no
        # es tuyo" para no filtrar la existencia de viajes ajenos.
        raise SinViajeActivoError()
    # CU-O14 paso 3 / A2: si quien consulta es el conductor, el detalle
    # también incluye nombre de pila y calificación del pasajero (nunca
    # teléfono ni ubicaciones) — mismo enriquecimiento que la lista de
    # historial, reutilizado aquí porque este es el único endpoint de
    # detalle por id (también usado para seguir un viaje activo en vivo).
    if viaje.get("conductor_id") == actor.usuario_id:
        viaje = await service_historial.enriquecer_con_pasajero(db, viaje)
    return to_out(viaje)
