import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.config import get_settings
from src.core.db_mongo import get_database
from src.core.exceptions import DomainError
from src.core.rbac import Actor, get_current_actor, require_roles
from src.viajes import schemas, service, service_compartir, service_historial

router = APIRouter(prefix="/viajes", tags=["viajes"])

_pasajero = require_roles("pasajero")
_conductor = require_roles("conductor")


class RolNoDisponibleError(DomainError):
    def __init__(self, rol: str) -> None:
        super().__init__(code="ROL_NO_DISPONIBLE", message=f"Tu cuenta no tiene el rol '{rol}'", status_code=403)


class TokenInternoInvalidoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="TOKEN_INTERNO_INVALIDO", message="Token interno inválido", status_code=403)


# Sección 1.5 de ux_complementaria.md: `POST /viajes/{id}/disparar-programado`
# lo llama `dag_disparar_viajes_programados` (Airflow, misma red interna de
# docker-compose) -- nunca un usuario final, así que no tiene sentido pedirle
# un Bearer token de sesión. Se protege con un secreto compartido simple
# (`internal_api_token`, ver core/config.py) comparado con
# `secrets.compare_digest` (evita timing attacks, mismo criterio que
# cualquier comparación de secreto en este proyecto).
async def _verificar_token_interno(x_internal_token: str | None = Header(default=None)) -> None:
    esperado = get_settings().internal_api_token
    if not x_internal_token or not secrets.compare_digest(x_internal_token, esperado):
        raise TokenInternoInvalidoError()


def to_out(doc: dict) -> schemas.ViajeOut:
    return schemas.ViajeOut(
        id=doc["_id"],
        pasajero_id=doc["pasajero_id"],
        conductor_id=doc.get("conductor_id"),
        vehiculo_id=doc.get("vehiculo_id"),
        estado=doc["estado"],
        origen_lat=doc["origen_lat"],
        origen_lon=doc["origen_lon"],
        origen_direccion=doc["origen_direccion"],
        destino_lat=doc.get("destino_lat"),
        destino_lon=doc.get("destino_lon"),
        destino_direccion=doc.get("destino_direccion"),
        franja=doc["franja"],
        ts_programado=doc.get("ts_programado"),
        ts_solicitud=doc["ts_solicitud"],
        ts_asignacion=doc.get("ts_asignacion"),
        ts_llegada_origen=doc.get("ts_llegada_origen"),
        ts_inicio=doc.get("ts_inicio"),
        ts_fin=doc.get("ts_fin"),
        km_recorridos=doc.get("km_recorridos"),
        min_espera=doc.get("min_espera"),
        tarifa_estimada=doc.get("tarifa_estimada"),
        tarifa_final=doc.get("tarifa_final"),
        motivo_cancelacion=doc.get("motivo_cancelacion"),
        conductor_nombre=doc.get("conductor_nombre"),
        conductor_calificacion=doc.get("conductor_calificacion"),
        conductor_foto_url=doc.get("conductor_foto_url"),
        vehiculo_placa=doc.get("vehiculo_placa"),
        vehiculo_marca=doc.get("vehiculo_marca"),
        vehiculo_color=doc.get("vehiculo_color"),
        calificacion_pasajero_a_conductor=doc.get("calificacion_pasajero_a_conductor"),
        calificacion_conductor_a_pasajero=doc.get("calificacion_conductor_a_pasajero"),
        pasajero_nombre=doc.get("pasajero_nombre"),
        pasajero_calificacion=doc.get("pasajero_calificacion"),
    )


@router.post("", response_model=schemas.ViajeOut, status_code=201)
async def solicitar_viaje(
    body: schemas.SolicitarViajeRequest,
    actor: Actor = Depends(_pasajero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viaje = await service.solicitar_viaje(db, pasajero_id=actor.usuario_id, body=body)
    return to_out(viaje)


@router.post("/activo/cancelar", response_model=schemas.ViajeOut)
async def cancelar_viaje(
    actor: Actor = Depends(_pasajero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viaje = await service.cancelar_viaje_pasajero(db, pasajero_id=actor.usuario_id)
    return to_out(viaje)


@router.post(
    "/{viaje_id}/disparar-programado",
    response_model=schemas.ViajeOut,
    dependencies=[Depends(_verificar_token_interno)],
)
async def disparar_viaje_programado(
    viaje_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viaje = await service.disparar_viaje_programado(db, viaje_id=viaje_id)
    return to_out(viaje)


@router.post("/activo/compartir", response_model=schemas.CompartirViajeOut)
async def compartir_viaje_activo(
    actor: Actor = Depends(_pasajero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    token = await service_compartir.generar_token_compartir(db, pasajero_id=actor.usuario_id)
    return schemas.CompartirViajeOut(token=token)


@router.get("/activo", response_model=schemas.ViajeOut | None)
async def obtener_viaje_activo(
    actor: Actor = Depends(_pasajero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # No tener un viaje activo es un estado normal (la mayoría del tiempo),
    # no una condición de error — 200 con cuerpo vacío, nunca 404. Distinto
    # de `SinViajeActivoError` (sigue siendo 404 en /activo/cancelar, donde
    # sí es un error intentar cancelar algo que no existe).
    viaje = await service.obtener_viaje_activo(db, pasajero_id=actor.usuario_id)
    return to_out(viaje) if viaje is not None else None


@router.get("/conductor/activo", response_model=schemas.ViajeOut | None)
async def obtener_viaje_activo_conductor(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viaje = await service.obtener_viaje_activo_conductor(db, conductor_id=actor.usuario_id)
    return to_out(viaje) if viaje is not None else None


@router.get("", response_model=schemas.HistorialOut)
async def listar_historial(
    rol: str = Query(..., pattern="^(pasajero|conductor)$"),
    estado: str | None = Query(default=None, pattern="^(FINALIZADO|CANCELADO)$"),
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if rol not in actor.roles:
        raise RolNoDisponibleError(rol)

    viajes, total = await service_historial.listar_historial(
        db, usuario_id=actor.usuario_id, rol=rol, estado=estado, desde=desde, hasta=hasta, pagina=pagina, limite=limite
    )
    return schemas.HistorialOut(viajes=[to_out(v) for v in viajes], total=total, pagina=pagina, limite=limite)


@router.get("/estimacion-ruta", response_model=schemas.EstimacionRutaOut)
async def obtener_estimacion_ruta(
    origen_lat: float,
    origen_lon: float,
    destino_lat: float,
    destino_lon: float,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Directions API no soporta CORS — se pide siempre desde aquí, nunca
    # directo desde el navegador (hallazgo de pruebas reales, ver
    # service.estimar_ruta). Cualquier actor autenticado puede pedirla
    # (pasajero y conductor la usan ambos).
    return await service.estimar_ruta(
        db, origen_lat=origen_lat, origen_lon=origen_lon, destino_lat=destino_lat, destino_lon=destino_lon
    )


_coordinador_operaciones = require_roles("coordinador_operaciones")


@router.get("/panel-tactico/activos", response_model=list[schemas.ViajeActivoOut])
async def listar_viajes_activos(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_coordinador_operaciones),
):
    viajes = await service.listar_viajes_activos(db)
    return [
        schemas.ViajeActivoOut(
            id=v["_id"], pasajero_id=v["pasajero_id"], conductor_id=v.get("conductor_id"),
            estado=v["estado"], ts_solicitud=v["ts_solicitud"],
        )
        for v in viajes
    ]


@router.get("/panel-tactico/sin-conductor-cancelados", response_model=list[schemas.ViajeSinConductorCanceladoOut])
async def listar_sin_conductor_y_cancelados(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_coordinador_operaciones),
):
    viajes = await service.listar_sin_conductor_y_cancelados_hoy(db)
    return [
        schemas.ViajeSinConductorCanceladoOut(
            id=v["_id"], estado=v["estado"], motivo_cancelacion=v.get("motivo_cancelacion"),
            actor_cancelacion=v.get("actor_cancelacion"), ts_solicitud=v["ts_solicitud"],
        )
        for v in viajes
    ]


@router.get("/panel-tactico/tiempo-asignacion", response_model=list[schemas.TiempoAsignacionOut])
async def obtener_tiempo_asignacion(
    _actor: Actor = Depends(_coordinador_operaciones),
):
    filas = service.obtener_tiempo_asignacion()
    return [schemas.TiempoAsignacionOut(**f) for f in filas]


@router.get("/panel-tactico/tasa-cancelacion", response_model=list[schemas.TasaCancelacionOut])
async def obtener_tasa_cancelacion(
    _actor: Actor = Depends(_coordinador_operaciones),
):
    filas = service.obtener_tasa_cancelacion()
    return [schemas.TasaCancelacionOut(**f) for f in filas]


# Sección 3.3 de ux_complementaria.md: historial navegable de todos los
# viajes de la cooperativa -- acceso restringido por rol (principio de
# mínimo privilegio ya aplicado en Administración).
_historial_global_roles = require_roles(
    "coordinador_operaciones", "supervisor_cumplimiento", "gerencia", "admin_sistema"
)


@router.get("/historial-global", response_model=schemas.HistorialOut)
async def listar_historial_global(
    texto: str | None = None,
    estado: str | None = Query(default=None, pattern="^(FINALIZADO|PAGADO|CANCELADO|SIN_CONDUCTOR)$"),
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=20, ge=1, le=100),
    actor: Actor = Depends(_historial_global_roles),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    viajes, total = await service_historial.listar_historial_global(
        db, texto=texto, estado=estado, desde=desde, hasta=hasta, pagina=pagina, limite=limite
    )
    return schemas.HistorialOut(viajes=[to_out(v) for v in viajes], total=total, pagina=pagina, limite=limite)
