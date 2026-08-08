from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.mantenimiento import schemas, service

router = APIRouter(prefix="/mantenimiento", tags=["mantenimiento"])

_jefe_mantenimiento = require_roles("jefe_mantenimiento")


def _to_out(doc: dict, placas: dict[str, str] | None = None) -> schemas.OrdenOut:
    placas = placas or {}
    return schemas.OrdenOut(
        id=doc["_id"],
        vehiculo_id=doc["vehiculo_id"],
        vehiculo_placa=placas.get(doc["vehiculo_id"]),
        tipo=doc["tipo"],
        estado=doc["estado"],
        descripcion=doc["descripcion"],
        km_entrada=doc["km_entrada"],
        km_salida=doc.get("km_salida"),
        taller=doc["taller"],
        fecha_programada=doc["fecha_programada"],
        fecha_cierre=doc.get("fecha_cierre"),
        costo_total=doc.get("costo_total"),
        orden_madre_id=doc.get("orden_madre_id"),
        repuestos_estimados=doc.get("repuestos_estimados", []),
        repuestos_consumidos=doc.get("repuestos_consumidos", []),
        horas_taller=doc.get("horas_taller"),
    )


@router.get("/vehiculos/buscar", response_model=list[schemas.VehiculoBusquedaOut])
async def buscar_vehiculo(
    placa: str = Query(min_length=1),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    vehiculos = await service.buscar_vehiculo_por_placa(db, placa=placa)
    return [
        schemas.VehiculoBusquedaOut(
            id=v["_id"],
            placa=v["placa"],
            marca=v["marca"],
            modelo=v["modelo"],
            estado_habilitacion=v["estado_habilitacion"],
        )
        for v in vehiculos
    ]


@router.post("/ordenes", response_model=schemas.OrdenOut, status_code=201)
async def crear_orden(
    body: schemas.OrdenCrearRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    orden = await service.crear_orden(
        db,
        dispatcher,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        vehiculo_id=body.vehiculo_id,
        tipo=body.tipo,
        descripcion=body.descripcion,
        km_entrada=body.km_entrada,
        taller=body.taller,
        fecha_programada=body.fecha_programada,
        retirar_vehiculo=body.retirar_vehiculo,
        repuestos_estimados=body.repuestos_estimados,
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.get("/ordenes", response_model=schemas.OrdenListOut)
async def listar_ordenes(
    estado: str | None = Query(default=None),
    vehiculo_id: str | None = Query(default=None),
    placa: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    ordenes, total = await service.listar_ordenes(
        db, estado=estado, vehiculo_id=vehiculo_id, placa=placa, limit=limit, offset=offset
    )
    placas = await service.obtener_placas_vehiculos(db, {o["vehiculo_id"] for o in ordenes})
    return schemas.OrdenListOut(items=[_to_out(o, placas) for o in ordenes], total=total)


@router.post("/ordenes/{orden_id}/taller", response_model=schemas.OrdenOut)
async def marcar_en_taller(
    orden_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    orden = await service.marcar_en_taller(db, orden_id=orden_id)
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.post("/ordenes/{orden_id}/cierre", response_model=schemas.OrdenOut)
async def cerrar_orden(
    orden_id: str,
    body: schemas.OrdenCerrarRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    orden = await service.cerrar_orden(
        db, dispatcher, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), orden_id=orden_id, body=body
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.post("/ordenes/{orden_id}/anulacion", response_model=schemas.OrdenOut)
async def anular_orden(
    orden_id: str,
    body: schemas.OrdenAnularRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.anular_orden(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), orden_id=orden_id, motivo=body.motivo
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.get("/panel-tactico/vehiculos-retirados", response_model=list[schemas.VehiculoRetiradoOut])
async def listar_vehiculos_retirados(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    vehiculos = await service.listar_vehiculos_retirados(db)
    return [schemas.VehiculoRetiradoOut(**v) for v in vehiculos]


@router.get("/panel-tactico/cumplimiento-preventivo", response_model=list[schemas.CumplimientoPreventivoOut])
async def obtener_cumplimiento_plan_preventivo(
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    filas = service.obtener_cumplimiento_plan_preventivo()
    return [schemas.CumplimientoPreventivoOut(**f) for f in filas]


@router.get("/panel-tactico/costo-top-vehiculos", response_model=list[schemas.CostoMantenimientoVehiculoOut])
async def obtener_costo_mantenimiento_top(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    filas = await service.obtener_costo_mantenimiento_top(db)
    return [schemas.CostoMantenimientoVehiculoOut(**f) for f in filas]


# Nivel estratégico — Panel de Estado y Costo de Flota (OE2b,
# nivel_estrategico.md §3.2.b). La spec lo asigna a `gerencia` +
# `junta_socios`. **Decisión aprobada: el rol `junta_socios` NO se crea**
# (no existe en `core/rbac.py::ROLES`, y crear un rol sin cuenta ni pantalla
# propias repetiría el patrón muerto de `integracion_externa`) -- los
# dashboards que la spec le asigna quedan bajo `gerencia`, el otro rol que la
# propia spec ya lista para todos ellos. Se suma `jefe_mantenimiento` por ser
# el dominio dueño del dato (mismo criterio que en OE2a con
# `coordinador_operaciones`).
_estado_costo_flota_estrategico = require_roles("gerencia", "jefe_mantenimiento")


@router.get("/panel-estrategico/estado-costo-flota", response_model=schemas.PanelEstadoCostoFlotaOut)
async def obtener_panel_estado_costo_flota(
    meses: int = Query(default=12, ge=1, le=36),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_estado_costo_flota_estrategico),
):
    datos = await service.obtener_panel_estado_costo_flota(db, meses=meses)
    return schemas.PanelEstadoCostoFlotaOut(**datos)
