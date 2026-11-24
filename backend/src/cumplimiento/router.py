from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.cumplimiento import schemas, service

router = APIRouter(prefix="/cumplimiento", tags=["cumplimiento"])

_supervisor_cumplimiento = require_roles("supervisor_cumplimiento")
_conductor = require_roles("conductor")


def _mi_documento_to_out(doc: dict) -> schemas.MiDocumentoOut:
    return schemas.MiDocumentoOut(
        id=doc["_id"],
        tipo=doc["tipo"],
        fecha_vencimiento=doc.get("fecha_vencimiento"),
        estado_verificacion=doc["estado_verificacion"],
        dias_restantes=doc.get("dias_restantes"),
        tiene_renovacion_pendiente=doc.get("renovacion_pendiente") is not None,
        archivo_id=doc.get("url_objeto"),
    )


# Autoservicio del conductor (cierre del gap real: "Buscar renovaciones
# pendientes" estaba condenada a quedar vacía para siempre porque nunca
# existió ninguna pantalla desde donde generar una). Solo lectura de los
# documentos propios, acotada por `actor.usuario_id` -- nunca por un id que
# venga del cliente.
@router.get("/documentos/mios", response_model=list[schemas.MiDocumentoOut])
async def listar_mis_documentos(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    documentos = await service.listar_mis_documentos(db, conductor_id=actor.usuario_id)
    return [_mi_documento_to_out(d) for d in documentos]


# Consulta rápida del estado documental de un socio, para personal interno.
# Mismo servicio y mismo criterio de propiedad que `/documentos/mios` (los
# documentos del conductor MÁS los de sus vehículos) -- solo cambia de quién
# se consulta y quién puede hacerlo. `admin_captacion` está incluido porque es
# quien aprueba la postulación que originó esos documentos y necesita poder
# revisarlos después; `coordinador_flota` porque es quien decide si un socio
# sale a operar. Es de SOLO LECTURA: ninguna acción de bloqueo cuelga de acá.
_consulta_documental_interna = require_roles(
    "supervisor_cumplimiento", "admin_captacion", "coordinador_flota", "admin_sistema", "gerencia"
)


@router.get("/documentos/conductor/{conductor_id}", response_model=list[schemas.MiDocumentoOut])
async def listar_documentos_de_conductor(
    conductor_id: str,
    _actor: Actor = Depends(_consulta_documental_interna),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    documentos = await service.listar_mis_documentos(db, conductor_id=conductor_id)
    return [_mi_documento_to_out(d) for d in documentos]


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
            archivo_id=d.get("url_objeto"),
            archivo_id_propuesto=d["renovacion_pendiente"].get("url_objeto"),
        )
        for d in documentos
    ]


@router.post("/documentos/{documento_id}/renovacion")
async def subir_renovacion(
    documento_id: str,
    body: schemas.RenovacionSubirRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    documento = await service.subir_renovacion(
        db,
        actor_id=actor.usuario_id,
        documento_id=documento_id,
        archivo_id=body.archivo_id,
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
    # OR-gate con `gerencia` -- ronda de mejoras (agosto 2026, punto 4 corregido):
    # el KPI "Documentos vencidos" del panel ESTRATÉGICO de Cumplimiento Normativo
    # (gateado a gerencia+supervisor_cumplimiento, ver `_cumplimiento_normativo_estrategico`
    # más abajo) reusa este endpoint para su drill-down -- sin este OR-gate, gerencia
    # veía el KPI pero el clic siempre daba 403 (confirmado real en navegador antes
    # de este cambio). No amplía el acceso al panel táctico completo (el sidebar de
    # `web-interno` sigue sin mostrárselo a gerencia), solo a esta lectura puntual.
    _actor: Actor = Depends(require_roles("supervisor_cumplimiento", "gerencia")),
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
            archivo_id=d.get("url_objeto"),
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
