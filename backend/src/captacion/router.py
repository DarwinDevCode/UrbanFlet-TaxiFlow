from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.captacion import schemas, service
from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, get_current_actor, require_roles

router = APIRouter(prefix="/captacion", tags=["captacion"])

_admin_captacion = require_roles("admin_captacion")


def _to_out(doc: dict) -> schemas.SolicitudOut:
    return schemas.SolicitudOut(
        id=doc["_id"],
        usuario_id=doc["usuario_id"],
        usuario_nombre=doc.get("usuario_nombre"),
        cedula=doc["cedula"],
        licencia_numero=doc["licencia_numero"],
        vehiculo=schemas.VehiculoInput(**doc["vehiculo"]),
        estado=doc["estado"],
        fecha_envio=doc["fecha_envio"],
        fecha_decision=doc["fecha_decision"],
        revision_reforzada=doc["revision_reforzada"],
        motivo_rechazo=doc["motivo_rechazo"],
        canal=doc.get("canal"),
        documentos=[
            schemas.DocumentoSolicitudOut(
                tipo=d["tipo"],
                propietario_tipo=d["propietario_tipo"],
                archivo_id=d["url_objeto"],
                fecha_emision=d.get("fecha_emision"),
                fecha_vencimiento=d.get("fecha_vencimiento"),
            )
            for d in doc.get("documentos", [])
        ],
    )


@router.post("/pasajeros/registro", response_model=schemas.PasajeroRegistroResponse, status_code=201)
async def registrar_pasajero(body: schemas.PasajeroRegistroRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    resultado = await service.registrar_pasajero(
        db,
        nombre=body.nombre,
        telefono=body.telefono,
        email=body.email,
        password=body.password,
        version_consentimiento=body.version_consentimiento,
        canal=body.canal,
    )
    return schemas.PasajeroRegistroResponse(**resultado)


@router.post("/solicitudes", response_model=schemas.SolicitudOut, status_code=201)
async def crear_solicitud(
    body: schemas.SolicitudCrearRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    solicitud = await service.crear_solicitud(
        db,
        dispatcher,
        nombre=body.nombre,
        telefono=body.telefono,
        email=body.email,
        password=body.password,
        cedula=body.cedula,
        licencia_numero=body.licencia_numero,
        vehiculo=body.vehiculo,
        documentos=body.documentos,
        enviar=body.enviar,
        canal=body.canal,
    )
    return _to_out(solicitud)


@router.post("/solicitudes/mia/documentos", response_model=schemas.SolicitudOut)
async def enviar_solicitud_con_documentos(
    body: schemas.EnviarSolicitudConDocumentosRequest,
    actor: Actor = Depends(get_current_actor),
    db: AsyncIOMotorDatabase = Depends(get_database),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    # Sin `require_roles`: el postulante recién creado no tiene NINGÚN rol
    # todavía (se asigna "conductor" solo al aprobar) -- cualquier actor
    # autenticado alcanza, el service ya acota la operación a SU PROPIA
    # solicitud en BORRADOR (`usuario_id == actor.usuario_id`).
    solicitud = await service.enviar_solicitud_con_documentos(
        db, dispatcher, actor_id=actor.usuario_id, documentos=body.documentos
    )
    return _to_out(solicitud)


@router.get("/solicitudes", response_model=schemas.SolicitudListOut)
async def listar_solicitudes(
    estado: str | None = Query(default=None),
    cedula: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_admin_captacion),
):
    solicitudes, total = await service.listar_solicitudes(
        db, estado=estado, cedula=cedula, limit=limit, offset=offset
    )
    return schemas.SolicitudListOut(items=[_to_out(s) for s in solicitudes], total=total)


@router.post("/solicitudes/{solicitud_id}/tomar", response_model=schemas.SolicitudOut)
async def tomar_solicitud(
    solicitud_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    actor: Actor = Depends(_admin_captacion),
):
    solicitud = await service.tomar_solicitud(
        db, solicitud_id=solicitud_id, verificador_id=actor.usuario_id, verificador_rol=",".join(actor.roles)
    )
    return _to_out(solicitud)


@router.post("/solicitudes/{solicitud_id}/decision", response_model=schemas.SolicitudOut)
async def decidir_solicitud(
    solicitud_id: str,
    body: schemas.SolicitudDecisionRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    actor: Actor = Depends(_admin_captacion),
    dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    solicitud = await service.decidir_solicitud(
        db,
        dispatcher,
        solicitud_id=solicitud_id,
        verificador_id=actor.usuario_id,
        verificador_rol=",".join(actor.roles),
        decision=body.decision,
        motivo=body.motivo,
    )
    return _to_out(solicitud)


@router.get("/panel-tactico/referidos-pendientes", response_model=list[schemas.ReferidoPendienteOut])
async def listar_referidos_pendientes(
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_admin_captacion),
):
    referidos = await service.listar_referidos_pendientes(db)
    return [
        schemas.ReferidoPendienteOut(
            id=r["_id"],
            referente_id=r["referente_id"],
            referido_id=r["referido_id"],
            canal=r["canal"],
            estado_incentivo=r["estado_incentivo"],
            fecha_referido=r["fecha_referido"],
        )
        for r in referidos
    ]


@router.get("/panel-tactico/conversion", response_model=list[schemas.ConversionCaptacionOut])
async def obtener_conversion_captacion(
    _actor: Actor = Depends(_admin_captacion),
):
    filas = service.obtener_conversion_captacion()
    return [schemas.ConversionCaptacionOut(**f) for f in filas]


@router.get("/panel-tactico/altas-retencion", response_model=list[schemas.AltasRetencionCanalOut])
async def obtener_altas_retencion_canal(
    _actor: Actor = Depends(_admin_captacion),
):
    filas = service.obtener_altas_retencion_canal()
    return [schemas.AltasRetencionCanalOut(**f) for f in filas]


# Nivel estratégico — Panel de Crecimiento Estratégico (OE1,
# nivel_estrategico.md §3.1). La spec lo asigna a `gerencia`; se suma
# `admin_captacion` por ser el dominio dueño del dato.
_crecimiento_estrategico = require_roles("gerencia", "admin_captacion")


@router.get("/panel-estrategico/crecimiento", response_model=schemas.PanelCrecimientoOut)
async def obtener_panel_crecimiento(
    meses: int = Query(default=12, ge=1, le=60),
    _actor: Actor = Depends(_crecimiento_estrategico),
):
    return schemas.PanelCrecimientoOut(**service.obtener_panel_crecimiento(meses=meses))
