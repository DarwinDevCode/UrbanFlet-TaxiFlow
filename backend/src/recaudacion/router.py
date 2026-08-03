from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.db_mongo import get_database
from src.core.rbac import Actor, require_roles
from src.recaudacion import schemas, service

router = APIRouter(prefix="/pagos", tags=["recaudacion"])

_conductor = require_roles("conductor")
_admin_financiero = require_roles("admin_financiero")


def to_out(doc: dict, nombres: dict[str, str] | None = None) -> schemas.PagoOut:
    nombres = nombres or {}
    return schemas.PagoOut(
        id=doc["_id"],
        viaje_id=doc["viaje_id"],
        conductor_id=doc["conductor_id"],
        conductor_nombre=nombres.get(doc["conductor_id"]),
        metodo=doc["metodo"],
        monto=doc["monto"],
        tarifa_final=doc["tarifa_final"],
        diferencia=doc.get("diferencia"),
        estado=doc["estado"],
        referencia_externa=doc.get("referencia_externa"),
        ts_registro=doc["ts_registro"],
        ts_confirmacion=doc.get("ts_confirmacion"),
        resuelto=doc.get("resuelto", False),
        resolucion_motivo=doc.get("resolucion_motivo"),
        resolucion_aceptado=doc.get("resolucion_aceptado"),
        resolucion_autorizador_id=doc.get("resolucion_autorizador_id"),
        resolucion_ts=doc.get("resolucion_ts"),
    )


def _viaje_sin_pago_to_out(doc: dict, nombres: dict[str, str] | None = None) -> schemas.ViajeSinPagoOut:
    nombres = nombres or {}
    return schemas.ViajeSinPagoOut(
        viaje_id=doc["viaje_id"],
        conductor_id=doc["conductor_id"],
        conductor_nombre=nombres.get(doc["conductor_id"]),
        tarifa_final=doc["tarifa_final"],
        ts_fin=doc["ts_fin"],
    )


def _movimiento_to_out(doc: dict) -> schemas.MovimientoOut:
    return schemas.MovimientoOut(
        id=doc["_id"],
        viaje_id=doc["viaje_id"],
        tipo=doc["tipo"],
        monto_firmado=doc["monto_firmado"],
        comision_version_id=doc.get("comision_version_id"),
        motivo=doc.get("motivo"),
        autorizador_id=doc.get("autorizador_id"),
        ts=doc["ts"],
        liquidacion_id=doc.get("liquidacion_id"),
    )


def _liquidacion_to_out(
    doc: dict, nombres: dict[str, str] | None = None, revision: dict[str, int] | None = None
) -> schemas.LiquidacionOut:
    nombres = nombres or {}
    revision = revision or {}
    return schemas.LiquidacionOut(
        id=doc["_id"],
        conductor_id=doc["conductor_id"],
        conductor_nombre=nombres.get(doc["conductor_id"]),
        periodo_inicio=doc["periodo_inicio"],
        periodo_fin=doc["periodo_fin"],
        estado=doc["estado"],
        bruto=doc["bruto"],
        comisiones=doc["comisiones"],
        ajustes=doc["ajustes"],
        neto=doc["neto"],
        saldo=doc["saldo"],
        detalle=[schemas.LiquidacionDetalleViajeOut(**d) for d in doc["detalle"]],
        ts_emision=doc["ts_emision"],
        ts_aprobacion=doc.get("ts_aprobacion"),
        ts_pago=doc.get("ts_pago"),
        aprobador_id=doc.get("aprobador_id"),
        observacion_motivo=doc.get("observacion_motivo"),
        viajes_en_revision=revision.get(doc["_id"], 0),
    )


@router.post("/efectivo", response_model=schemas.PagoOut, status_code=201)
async def registrar_pago_efectivo(
    body: schemas.RegistrarPagoRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    pago = await service.registrar_pago_efectivo(
        db, conductor_id=actor.usuario_id, viaje_id=body.viaje_id, monto_cobrado=body.monto_cobrado
    )
    nombres = await service.obtener_nombres_conductores(db, {pago["conductor_id"]})
    return to_out(pago, nombres)


@router.get("/discrepancias", response_model=schemas.BandejaDiscrepanciasOut)
async def listar_discrepancias(
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    discrepancias, viajes_sin_pago = await service.listar_bandeja_discrepancias(db)
    nombres = await service.obtener_nombres_conductores(
        db, {d["conductor_id"] for d in discrepancias} | {v["conductor_id"] for v in viajes_sin_pago}
    )
    return schemas.BandejaDiscrepanciasOut(
        discrepancias=[to_out(p, nombres) for p in discrepancias],
        viajes_sin_pago=[_viaje_sin_pago_to_out(v, nombres) for v in viajes_sin_pago],
    )


@router.post("/{pago_id}/resolver", response_model=schemas.PagoOut)
async def resolver_discrepancia(
    pago_id: str,
    body: schemas.ResolverDiscrepanciaRequest,
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    pago = await service.resolver_discrepancia(
        db, pago_id=pago_id, autorizador_id=actor.usuario_id, aceptar=body.aceptar, motivo=body.motivo
    )
    nombres = await service.obtener_nombres_conductores(db, {pago["conductor_id"]})
    return to_out(pago, nombres)


@router.post("/{viaje_id}/ajuste", response_model=schemas.MovimientoOut, status_code=201)
async def crear_ajuste(
    viaje_id: str,
    body: schemas.CrearAjusteRequest,
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """CU-O10 A2: ajuste autorizado sobre un viaje ya recaudado — crea un
    movimiento `AJUSTE` adicional y trazable, nunca modifica COMISION/
    NETO_SOCIO. Distinto de `/liquidaciones/{id}/responder-observacion`
    (CU-O11 A2, ajuste sobre una liquidación ya emitida en respuesta a una
    observación del socio)."""
    mov = await service.crear_ajuste_movimiento(
        db, viaje_id=viaje_id, monto=body.monto, motivo=body.motivo, autorizador_id=actor.usuario_id
    )
    return _movimiento_to_out(mov)


@router.get("/panel-tactico/tasa-discrepancias", response_model=list[schemas.TasaDiscrepanciasOut])
async def obtener_tasa_discrepancias(
    _actor: Actor = Depends(_admin_financiero),
):
    filas = service.obtener_tasa_discrepancias()
    return [schemas.TasaDiscrepanciasOut(**f) for f in filas]


router_liquidaciones = APIRouter(prefix="/liquidaciones", tags=["recaudacion"])


@router_liquidaciones.get("/panel-tactico/margen-comision", response_model=list[schemas.MargenComisionOut])
async def obtener_margen_comision(
    _actor: Actor = Depends(_admin_financiero),
):
    filas = service.obtener_margen_comision()
    return [schemas.MargenComisionOut(**f) for f in filas]


@router_liquidaciones.post("/generar", response_model=schemas.GenerarLiquidacionesResponse, status_code=201)
async def generar_liquidaciones(
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    resultado = await service.generar_liquidaciones(db, autorizador_id=actor.usuario_id)
    nombres = await service.obtener_nombres_conductores(db, {doc["conductor_id"] for doc in resultado["generadas"]})
    return schemas.GenerarLiquidacionesResponse(
        periodo_inicio=resultado["periodo_inicio"],
        periodo_fin=resultado["periodo_fin"],
        generadas=[_liquidacion_to_out(doc, nombres) for doc in resultado["generadas"]],
        ya_existian=resultado["ya_existian"],
    )


@router_liquidaciones.get("", response_model=schemas.LiquidacionListOut)
async def listar_liquidaciones(
    estado: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidaciones = await service.listar_liquidaciones(db, estado=estado, limit=limit, offset=offset)
    total = await service.contar_liquidaciones(db, estado=estado)
    nombres = await service.obtener_nombres_conductores(db, {doc["conductor_id"] for doc in liquidaciones})
    revision = await service.contar_viajes_en_revision(db, liquidaciones=liquidaciones)
    return schemas.LiquidacionListOut(
        items=[_liquidacion_to_out(doc, nombres, revision) for doc in liquidaciones], total=total
    )


@router_liquidaciones.post("/{liquidacion_id}/aprobar", response_model=schemas.LiquidacionOut)
async def aprobar_liquidacion(
    liquidacion_id: str,
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidacion = await service.aprobar_liquidacion(db, liquidacion_id=liquidacion_id, aprobador_id=actor.usuario_id)
    nombres = await service.obtener_nombres_conductores(db, {liquidacion["conductor_id"]})
    return _liquidacion_to_out(liquidacion, nombres)


@router_liquidaciones.post("/{liquidacion_id}/pagar", response_model=schemas.LiquidacionOut)
async def pagar_liquidacion(
    liquidacion_id: str,
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidacion = await service.pagar_liquidacion(db, liquidacion_id=liquidacion_id, autorizador_id=actor.usuario_id)
    nombres = await service.obtener_nombres_conductores(db, {liquidacion["conductor_id"]})
    return _liquidacion_to_out(liquidacion, nombres)


@router_liquidaciones.get("/mias", response_model=list[schemas.LiquidacionOut])
async def listar_mis_liquidaciones(
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidaciones = await service.listar_liquidaciones(db, conductor_id=actor.usuario_id)
    nombres = await service.obtener_nombres_conductores(db, {doc["conductor_id"] for doc in liquidaciones})
    return [_liquidacion_to_out(doc, nombres) for doc in liquidaciones]


@router_liquidaciones.post("/{liquidacion_id}/observar", response_model=schemas.LiquidacionOut)
async def observar_liquidacion(
    liquidacion_id: str,
    body: schemas.ObservarLiquidacionRequest,
    actor: Actor = Depends(_conductor),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidacion = await service.observar_liquidacion(
        db, liquidacion_id=liquidacion_id, conductor_id=actor.usuario_id, motivo=body.motivo
    )
    nombres = await service.obtener_nombres_conductores(db, {liquidacion["conductor_id"]})
    return _liquidacion_to_out(liquidacion, nombres)


@router_liquidaciones.post("/{liquidacion_id}/responder-observacion", response_model=schemas.LiquidacionOut)
async def responder_observacion(
    liquidacion_id: str,
    body: schemas.ResponderObservacionRequest,
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    liquidacion = await service.responder_observacion(
        db,
        liquidacion_id=liquidacion_id,
        autorizador_id=actor.usuario_id,
        ratificar=body.ratificar,
        motivo=body.motivo,
        ajuste_monto=body.ajuste_monto,
    )
    nombres = await service.obtener_nombres_conductores(db, {liquidacion["conductor_id"]})
    return _liquidacion_to_out(liquidacion, nombres)


@router_liquidaciones.get("/alertas-saldo-negativo", response_model=list[schemas.AlertaSaldoNegativoOut])
async def listar_alertas_saldo_negativo(
    actor: Actor = Depends(_admin_financiero),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    alertas = await service.listar_alertas_saldo_negativo(db)
    nombres = await service.obtener_nombres_conductores(db, {a["conductor_id"] for a in alertas})
    return [
        schemas.AlertaSaldoNegativoOut(
            conductor_id=a["conductor_id"],
            conductor_nombre=nombres.get(a["conductor_id"]),
            periodos_consecutivos=a["periodos_consecutivos"],
            liquidaciones=[_liquidacion_to_out(doc, nombres) for doc in a["liquidaciones"]],
        )
        for a in alertas
    ]
