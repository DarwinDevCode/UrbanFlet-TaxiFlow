from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.cumplimiento import schemas, service

router = APIRouter(prefix="/cumplimiento", tags=["cumplimiento"])

_supervisor_cumplimiento = require_roles("supervisor_cumplimiento")


@router.post("/control-vigencia", response_model=schemas.ControlVigenciaResultado)
async def ejecutar_control_vigencia(
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
    _actor: Actor = Depends(_supervisor_cumplimiento),
):
    # Disparo manual/administrativo del job diario (06:00 en producción). La
    # programación real (cron/Airflow) es infraestructura de despliegue, no
    # de dominio — se deja fuera de esta fase; este endpoint permite
    # ejecutarlo bajo demanda y es lo que un scheduler futuro invocaría.
    resultado = await service.ejecutar_control_vigencia_documental(db, dispatcher)
    return schemas.ControlVigenciaResultado(**resultado)


@router.get("/documentos/renovaciones-pendientes", response_model=list[schemas.RenovacionPendienteOut])
async def listar_renovaciones_pendientes(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_supervisor_cumplimiento),
):
    documentos = await service.listar_renovaciones_pendientes(db)
    nombres = await service.resolver_nombres_propietarios(db, documentos)
    return [
        schemas.RenovacionPendienteOut(
            documento_id=d["_id"],
            tipo=d["tipo"],
            propietario_tipo=d["propietario_tipo"],
            propietario_id=d["propietario_id"],
            propietario_nombre=nombres.get(d["propietario_id"]),
            fecha_vencimiento_actual=d.get("fecha_vencimiento"),
            fecha_vencimiento_propuesta=d["renovacion_pendiente"]["fecha_vencimiento"],
        )
        for d in documentos
    ]


@router.post("/documentos/{documento_id}/renovacion")
async def subir_renovacion(
    documento_id: str,
    body: schemas.RenovacionSubirRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    documento = await service.subir_renovacion(
        db,
        documento_id=documento_id,
        url_objeto=body.url_objeto,
        hash_archivo=body.hash_archivo,
        fecha_vencimiento=body.fecha_vencimiento,
    )
    return {"documento_id": documento["_id"], "estado": "RENOVACION_PENDIENTE"}


@router.post("/documentos/{documento_id}/renovacion/verificacion")
async def verificar_renovacion(
    documento_id: str,
    body: schemas.RenovacionVerificarRequest,
    actor: Actor = Depends(_supervisor_cumplimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    documento = await service.verificar_renovacion(
        db,
        dispatcher,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        documento_id=documento_id,
        aprobar=body.aprobar,
        motivo=body.motivo,
    )
    return {
        "documento_id": documento["_id"],
        "estado_verificacion": documento.get("estado_verificacion"),
        "fecha_vencimiento": documento.get("fecha_vencimiento"),
    }


@router.get("/panel-tactico/documentos-por-vencer", response_model=list[schemas.DocumentoVencimientoOut])
async def listar_documentos_por_vencer(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_supervisor_cumplimiento),
):
    documentos = await service.listar_documentos_vencidos_y_por_vencer(db)
    return [
        schemas.DocumentoVencimientoOut(
            documento_id=d["_id"],
            tipo=d["tipo"],
            propietario_tipo=d["propietario_tipo"],
            propietario_id=d["propietario_id"],
            propietario_nombre=d.get("propietario_nombre"),
            fecha_vencimiento=d.get("fecha_vencimiento"),
            estado_verificacion=d["estado_verificacion"],
            dias_restantes=d.get("dias_restantes"),
        )
        for d in documentos
    ]


@router.get("/panel-tactico/documentacion-vigente", response_model=list[schemas.DocumentacionVigenteOut])
async def obtener_documentacion_vigente(
    _actor: Actor = Depends(_supervisor_cumplimiento),
):
    filas = service.obtener_documentacion_vigente()
    return [schemas.DocumentacionVigenteOut(**f) for f in filas]


@router.get("/panel-tactico/documentacion-tendencia", response_model=list[schemas.DocumentacionVigenteOut])
async def obtener_documentacion_tendencia(
    _actor: Actor = Depends(_supervisor_cumplimiento),
):
    filas = service.obtener_documentacion_tendencia()
    return [schemas.DocumentacionVigenteOut(**f) for f in filas]


# Nivel estratégico — Panel de Cumplimiento Normativo (OE6a,
# nivel_estrategico.md §3.6.a). La spec lo asigna a `gerencia` +
# `supervisor_cumplimiento` (lectura).
_cumplimiento_normativo_estrategico = require_roles("gerencia", "supervisor_cumplimiento")


@router.get("/panel-estrategico/cumplimiento-normativo", response_model=schemas.PanelCumplimientoNormativoOut)
async def obtener_panel_cumplimiento_normativo(
    cortes: int = Query(default=12, ge=1, le=60),
    _actor: Actor = Depends(_cumplimiento_normativo_estrategico),
):
    return schemas.PanelCumplimientoNormativoOut(**service.obtener_panel_cumplimiento_normativo(cortes=cortes))
