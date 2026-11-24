from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.reportes_falla import schemas, service

router = APIRouter(prefix="/reportes-falla", tags=["reportes-falla"])

_conductor = require_roles("conductor")
_jefe_mantenimiento = require_roles("jefe_mantenimiento")


def _to_out(doc: dict) -> schemas.ReporteFallaOut:
    return schemas.ReporteFallaOut(
        id=doc["_id"],
        vehiculo_id=doc["vehiculo_id"],
        vehiculo_placa=doc.get("vehiculo_placa"),
        conductor_id=doc["conductor_id"],
        viaje_id=doc.get("viaje_id"),
        tipo_falla=doc["tipo_falla"],
        descripcion=doc["descripcion"],
        lat=doc["lat"],
        lon=doc["lon"],
        ts=doc["ts"],
        impide_continuar=doc["impide_continuar"],
        estado=doc["estado"],
        orden_id=doc.get("orden_id"),
        evidencias=doc.get("evidencias", []),
        motivo_descarte=doc.get("motivo_descarte"),
    )


@router.post("", response_model=schemas.ReporteFallaOut, status_code=201)
async def reportar_falla(
    body: schemas.ReportarFallaRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    doc = await service.crear_reporte_falla(
        db,
        conductor_id=actor.usuario_id,
        tipo_falla=body.tipo_falla,
        descripcion=body.descripcion,
        lat=body.lat,
        lon=body.lon,
        impide_continuar=body.impide_continuar,
        evidencias=body.evidencias,
        dispatcher=dispatcher,
    )
    return _to_out(doc)


# Autoservicio del conductor (Grupo B de la ronda de correcciones UX/UI): el
# conductor podía crear un reporte pero no volver a verlo -- el único listado
# que existía es la bandeja del Jefe de Mantenimiento de más abajo, que además
# devuelve los reportes de TODA la flota. Este endpoint es de solo lectura y
# está acotado por el propio `actor.usuario_id`, nunca por un id que venga del
# cliente: un conductor solo ve sus propios reportes. Declarado antes que
# `GET /reportes-falla` no por precedencia de rutas (no hay conflicto, el path
# es distinto) sino para que quede junto al resto del flujo del conductor.
@router.get("/mias", response_model=list[schemas.ReporteFallaOut])
async def listar_mis_reportes_falla(
    estado: str | None = None,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_reportes_falla(db, estado=estado, conductor_id=actor.usuario_id)
    return [_to_out(d) for d in docs]


# ---------------------------------------------------------------------------
# Ronda 2, Fase D: bandeja del Jefe de Mantenimiento sobre los reportes que
# llegan de la Fase C -- listar, convertir en orden (reusa
# mantenimiento.service.crear_orden y el selector de taller de la Ronda 1,
# ver reportes_falla/service.py), o descartar con motivo obligatorio.
# ---------------------------------------------------------------------------


# Auditoría/completado del flujo de fallas: el botón "Nuevo" de la bandeja de
# web-interno estaba deshabilitado a propósito ("los reportes los crea el
# conductor, no el Jefe de Mantenimiento") -- este endpoint lo habilita de
# verdad. Mismo modelo de datos y misma bandeja de `GET /reportes-falla` que
# el reporte del conductor (`POST /reportes-falla`), sin duplicar el listado
# ni distinguir visualmente el origen -- ver `service.py::
# crear_reporte_falla_staff` para el porqué de cada diferencia real (vehículo
# explícito en vez de inferido, sin viaje/impide_continuar, posición desde la
# última señal conocida en vez de geolocalización del dispositivo).
@router.post("/personal-interno", response_model=schemas.ReporteFallaOut, status_code=201)
async def reportar_falla_personal_interno(
    body: schemas.ReportarFallaStaffRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    doc = await service.crear_reporte_falla_staff(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        vehiculo_id=body.vehiculo_id,
        tipo_falla=body.tipo_falla,
        descripcion=body.descripcion,
        evidencias=body.evidencias,
        dispatcher=dispatcher,
    )
    return _to_out(doc)


@router.get("", response_model=list[schemas.ReporteFallaOut])
async def listar_reportes_falla(
    estado: str | None = None,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    docs = await service.listar_reportes_falla(db, estado=estado)
    return [_to_out(d) for d in docs]


@router.post("/{reporte_id}/convertir", response_model=schemas.ReporteFallaOut)
async def convertir_en_orden(
    reporte_id: str,
    body: schemas.ConvertirReporteRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    doc = await service.convertir_reporte_en_orden(
        db,
        dispatcher,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        reporte_id=reporte_id,
        body=body,
    )
    return _to_out(doc)


@router.patch("/{reporte_id}/correccion", response_model=schemas.ReporteFallaOut)
async def corregir_reporte(
    reporte_id: str,
    body: schemas.CorregirReporteRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.corregir_reporte(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        reporte_id=reporte_id,
        tipo_falla=body.tipo_falla,
        descripcion=body.descripcion,
        motivo=body.motivo,
    )
    return _to_out(doc)


@router.post("/{reporte_id}/descartar", response_model=schemas.ReporteFallaOut)
async def descartar_reporte(
    reporte_id: str,
    body: schemas.DescartarReporteRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await service.descartar_reporte(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), reporte_id=reporte_id, motivo=body.motivo
    )
    return _to_out(doc)
