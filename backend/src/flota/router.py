from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, get_current_actor, require_roles
from src.flota import schemas, service

router = APIRouter(prefix="/flota", tags=["flota"])

_conductor = require_roles("conductor")
_coordinador_flota = require_roles("coordinador_flota", "admin_plataforma")


@router.post("/turno/iniciar", response_model=schemas.TurnoOut)
async def iniciar_turno(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.iniciar_turno(db, conductor_id=actor.usuario_id)
    return schemas.TurnoOut(**resultado)


@router.post("/turno/terminar", response_model=schemas.TurnoOut)
async def terminar_turno(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.terminar_turno(db, conductor_id=actor.usuario_id)
    return schemas.TurnoOut(**resultado)


@router.post("/posiciones", response_model=schemas.PosicionReportarResponse)
async def reportar_posicion(
    body: schemas.PosicionReportarRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await service.reportar_posicion(db, conductor_id=actor.usuario_id, body=body)


@router.get("/cercanos", response_model=list[schemas.VehiculoCercanoOut])
async def listar_vehiculos_cercanos(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radio_m: float = Query(default=300, gt=0, le=5000),
    _actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    cercanos = await service.listar_vehiculos_cercanos(db, lat=lat, lon=lon, radio_m=radio_m)
    return [schemas.VehiculoCercanoOut(**c) for c in cercanos]


@router.get("/posicion/{conductor_id}", response_model=schemas.PosicionConductorOut)
async def obtener_posicion_conductor(
    conductor_id: str,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.obtener_posicion_conductor(db, actor_id=actor.usuario_id, conductor_id=conductor_id)
    return schemas.PosicionConductorOut(**resultado)


@router.get("/tablero", response_model=list[schemas.VehiculoEstadoOut])
async def listar_estado_flota(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_coordinador_flota),
):
    estados = await service.listar_estado_flota(db)
    return [schemas.VehiculoEstadoOut(**e) for e in estados]


@router.get("/panel-tactico/franja-activa", response_model=list[schemas.FlotaActivaFranjaOut])
async def obtener_flota_activa_franja(
    _actor: Actor = Depends(_coordinador_flota),
):
    filas = service.obtener_flota_activa_franja()
    return [schemas.FlotaActivaFranjaOut(**f) for f in filas]
