from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.notifications import NotificationDispatcher, get_notification_dispatcher
from src.core.rbac import Actor, require_roles
from src.mantenimiento import schemas, service

router = APIRouter(prefix="/mantenimiento", tags=["mantenimiento"])

_jefe_mantenimiento = require_roles("jefe_mantenimiento")
_conductor = require_roles("conductor")


def _to_out(doc: dict, placas: dict[str, str] | None = None) -> schemas.OrdenOut:
    placas = placas or {}
    mano_obra_estimada = doc.get("mano_obra_estimada") or 0.0
    repuestos_estimados = doc.get("repuestos_estimados", [])
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
        repuestos_estimados=repuestos_estimados,
        repuestos_consumidos=doc.get("repuestos_consumidos", []),
        horas_taller=doc.get("horas_taller"),
        proxima_km_preventivo=doc.get("proxima_km_preventivo"),
        evidencias=doc.get("evidencias", []),
        motivo_espera=doc.get("motivo_espera"),
        actividades=doc.get("actividades", []),
        mano_obra_estimada=mano_obra_estimada,
        # Ronda 2, Fase G (punto 1): `doc` ya trae `costo_estimado` calculado
        # cuando viene de la respuesta de cierre (service.cerrar_orden) --
        # en cualquier otra respuesta (crear/listar/etc.) se recalcula acá
        # desde los mismos 2 campos, nunca se persiste en Mongo.
        costo_estimado=doc.get("costo_estimado", service._costo_estimado(mano_obra_estimada, repuestos_estimados)),
        desviacion_costo_pct=doc.get("desviacion_costo_pct"),
        orden_encadenada_id=doc.get("orden_encadenada_id"),
    )


@router.get("/vehiculos/buscar", response_model=list[schemas.VehiculoBusquedaOut])
async def buscar_vehiculo(
    # Opcional: sin `placa` devuelve la flota activa completa, que es lo que
    # necesita el combobox de "Nueva orden" para filtrar del lado del cliente.
    # Con `placa` sigue funcionando igual que siempre (búsqueda parcial).
    placa: str = Query(default="", max_length=20),
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


@router.get("/vehiculos/mio/ficha", response_model=schemas.FichaVehiculoOut)
async def obtener_ficha_de_mi_vehiculo(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Autoservicio del conductor (ver `service.obtener_ficha_de_mi_vehiculo`):
    ruta literal `/mio/ficha`, declarada ANTES de `/vehiculos/{vehiculo_id}/ficha`
    para que FastAPI no la confunda con esa ruta paramétrica (mismo criterio
    ya aplicado por `/vehiculos/buscar`, también literal y declarada antes).
    Nunca recibe un `vehiculo_id` del cliente -- se resuelve siempre desde
    `actor.usuario_id`, así que no hay forma de pedir la ficha de otro socio."""
    ficha = await service.obtener_ficha_de_mi_vehiculo(db, conductor_id=actor.usuario_id)
    return schemas.FichaVehiculoOut(
        id=ficha["_id"],
        placa=ficha["placa"],
        marca=ficha["marca"],
        modelo=ficha["modelo"],
        estado_habilitacion=ficha["estado_habilitacion"],
        km_acumulado=ficha["km_acumulado"],
        fecha_ultima_intervencion=ficha["fecha_ultima_intervencion"],
        km_ultima_intervencion=ficha["km_ultima_intervencion"],
        proxima_km_preventivo=ficha["proxima_km_preventivo"],
        le_toca_preventivo=ficha["le_toca_preventivo"],
        umbral_km_preventivo=ficha["umbral_km_preventivo"],
    )


@router.patch("/vehiculos/{vehiculo_id}", response_model=schemas.VehiculoBusquedaOut)
async def editar_vehiculo(
    vehiculo_id: str,
    body: schemas.VehiculoEditarRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Cierra la U del CRUD de `vehiculos` (PROPUESTA_CRUD_Y_BAJA_LOGICA.md,
    Fase C): corrección de datos descriptivos mal cargados al aprobar la
    postulación. Solo los campos enviados se tocan (`exclude_unset`)."""
    vehiculo = await service.editar_vehiculo(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        vehiculo_id=vehiculo_id,
        cambios=body.model_dump(exclude_unset=True, exclude_none=True),
    )
    return schemas.VehiculoBusquedaOut(
        id=vehiculo["_id"],
        placa=vehiculo["placa"],
        marca=vehiculo["marca"],
        modelo=vehiculo["modelo"],
        estado_habilitacion=vehiculo["estado_habilitacion"],
    )


@router.post("/vehiculos/{vehiculo_id}/dar-de-baja", response_model=schemas.VehiculoBajaOut)
async def dar_de_baja_vehiculo(
    vehiculo_id: str,
    body: schemas.BajaVehiculoRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Decisión 3: saca el vehículo de la flota operativa de forma permanente
    (`estado_habilitacion = DADO_DE_BAJA`). Se rechaza con 409 si tiene una
    orden de mantenimiento abierta -- mismo patrón que la baja de una cuenta
    con un viaje en curso."""
    vehiculo = await service.dar_de_baja_vehiculo(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        vehiculo_id=vehiculo_id,
        motivo=body.motivo,
    )
    return schemas.VehiculoBajaOut(
        id=vehiculo["_id"],
        placa=vehiculo["placa"],
        estado_habilitacion=vehiculo["estado_habilitacion"],
        motivo_baja=vehiculo.get("motivo_baja"),
    )


@router.get("/vehiculos/{vehiculo_id}/ficha", response_model=schemas.FichaVehiculoOut)
async def obtener_ficha_vehiculo(
    vehiculo_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    _actor: Actor = Depends(_jefe_mantenimiento),
):
    ficha = await service.obtener_ficha_vehiculo(db, vehiculo_id=vehiculo_id)
    return schemas.FichaVehiculoOut(
        id=ficha["_id"],
        placa=ficha["placa"],
        marca=ficha["marca"],
        modelo=ficha["modelo"],
        estado_habilitacion=ficha["estado_habilitacion"],
        km_acumulado=ficha["km_acumulado"],
        fecha_ultima_intervencion=ficha["fecha_ultima_intervencion"],
        km_ultima_intervencion=ficha["km_ultima_intervencion"],
        proxima_km_preventivo=ficha["proxima_km_preventivo"],
        le_toca_preventivo=ficha["le_toca_preventivo"],
        umbral_km_preventivo=ficha["umbral_km_preventivo"],
    )


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
        mano_obra_estimada=body.mano_obra_estimada,
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
    # Cierre Tier 1-2, punto 2.5: OR-gate con `gerencia` en esta lectura
    # puntual -- alimenta el drill-down de "Cumplimiento preventivo" en el
    # Panel de Estado y Costo de Flota ESTRATÉGICO (que sí ve `gerencia`).
    # `_jefe_mantenimiento` (sin `gerencia`) se deja intacto en los otros 8
    # endpoints de este router, que son CRUD operativo. Mismo patrón que
    # `recaudacion/router.py::_discrepancias_estrategico` (punto 2.4) y
    # `cumplimiento/router.py::listar_documentos_por_vencer` (CLAUDE.md §17.11).
    _actor: Actor = Depends(require_roles("jefe_mantenimiento", "gerencia")),
):
    ordenes, total = await service.listar_ordenes(
        db, estado=estado, vehiculo_id=vehiculo_id, placa=placa, limit=limit, offset=offset
    )
    placas = await service.obtener_placas_vehiculos(db, {o["vehiculo_id"] for o in ordenes})
    return schemas.OrdenListOut(items=[_to_out(o, placas) for o in ordenes], total=total)


@router.post("/ordenes/{orden_id}/taller", response_model=schemas.OrdenOut)
async def marcar_en_taller(
    orden_id: str,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.marcar_en_taller(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), orden_id=orden_id
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.post("/ordenes/{orden_id}/espera-repuesto", response_model=schemas.OrdenOut)
async def marcar_esperando_repuesto(
    orden_id: str,
    body: schemas.OrdenEsperaRepuestoRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.marcar_esperando_repuesto(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), orden_id=orden_id, motivo=body.motivo
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.post("/ordenes/{orden_id}/reanudar", response_model=schemas.OrdenOut)
async def reanudar_taller(
    orden_id: str,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.reanudar_taller(
        db, actor_id=actor.usuario_id, actor_rol=",".join(actor.roles), orden_id=orden_id
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.patch("/ordenes/{orden_id}/correccion", response_model=schemas.OrdenOut)
async def corregir_orden(
    orden_id: str,
    body: schemas.CorregirOrdenRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.corregir_orden(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        orden_id=orden_id,
        descripcion=body.descripcion,
        taller=body.taller,
        fecha_programada=body.fecha_programada,
        repuestos_estimados=body.repuestos_estimados,
        mano_obra_estimada=body.mano_obra_estimada,
        motivo=body.motivo,
    )
    placas = await service.obtener_placas_vehiculos(db, {orden["vehiculo_id"]})
    return _to_out(orden, placas)


@router.post("/ordenes/{orden_id}/actividades", response_model=schemas.OrdenOut)
async def agregar_actividad(
    orden_id: str,
    body: schemas.ActividadCrearRequest,
    actor: Actor = Depends(_jefe_mantenimiento),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    orden = await service.agregar_actividad(
        db,
        actor_id=actor.usuario_id,
        actor_rol=",".join(actor.roles),
        orden_id=orden_id,
        detalle=body.detalle,
        evidencias=body.evidencias,
    )
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
