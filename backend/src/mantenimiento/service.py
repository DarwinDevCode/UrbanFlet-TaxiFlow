"""Mantenimiento — CU-O12 (registrar orden), CU-O13 (cerrar orden y
habilitar el vehículo).

Alcance de esta fase: se cubre el flujo principal de ambos CU y los
alternos con validación bloqueante (A2/A3 de CU-O13) y la anulación (A4 de
CU-O12). Quedan fuera de esta fase — no son huecos de la spec, son
dependencias de módulos que todavía no existen — la pre-orden automática por
umbral de kilometraje (A2 de CU-O12, necesita telemetría de flota agregada)
y la pre-orden por incidencia de viaje (A1 de CU-O12, necesita CU-O07 de
Fase 3).

Cada operación que muta más de una entidad de negocio (orden + vehículo)
está envuelta en `core.db_transaction.with_transaction` — el mismo patrón
introducido en Fase 1 para la cadena de aprobación de Captación.
"""

import uuid
from datetime import date, datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.core.notifications import NotificationDispatcher
from src.mantenimiento import schemas


class VehiculoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="VEHICULO_NO_ENCONTRADO", message="El vehículo no existe", status_code=404)


class OrdenNoEncontradaError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="ORDEN_NO_ENCONTRADA", message="La orden no existe", status_code=404)


class OrdenEstadoInvalidoError(DomainError):
    def __init__(self, esperado: str) -> None:
        super().__init__(
            code="ORDEN_ESTADO_INVALIDO", message=f"La orden debe estar en estado: {esperado}", status_code=409
        )


class KmSalidaMenorError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="KM_SALIDA_MENOR",
            message="El kilometraje de salida es menor al de entrada; marca ajuste_justificado con motivo",
            status_code=400,
        )


async def obtener_placas_vehiculos(db: AsyncIOMotorDatabase, vehiculo_ids: set[str]) -> dict[str, str]:
    """Resuelve `vehiculo_id` -> `placa` en un solo `$in`, para que la
    bandeja de órdenes (CU-O12/CU-O13) no muestre el UUID crudo del
    vehículo. Mismo criterio de batch que
    `captacion.service.enriquecer_con_usuario_nombre`."""
    vehiculo_ids = {v for v in vehiculo_ids if v}
    if not vehiculo_ids:
        return {}
    vehiculos = await db.vehiculos.find({"_id": {"$in": list(vehiculo_ids)}}).to_list(length=len(vehiculo_ids))
    return {v["_id"]: v["placa"] for v in vehiculos}


async def buscar_vehiculo_por_placa(db: AsyncIOMotorDatabase, *, placa: str) -> list[dict]:
    # Búsqueda de apoyo para el formulario de "crear orden" (necesita el
    # vehiculo_id, que el usuario no conoce de memoria, solo la placa).
    cursor = db.vehiculos.find({"placa": {"$regex": placa, "$options": "i"}}).limit(10)
    return await cursor.to_list(length=10)


async def crear_orden(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    vehiculo_id: str,
    tipo: str,
    descripcion: str,
    km_entrada: int,
    taller: str,
    fecha_programada: date,
    retirar_vehiculo: bool,
    repuestos_estimados: list[schemas.RepuestoInput],
) -> dict:
    vehiculo = await db.vehiculos.find_one({"_id": vehiculo_id})
    if vehiculo is None:
        raise VehiculoNoEncontradoError()

    orden_id = str(uuid.uuid4())
    orden = {
        "_id": orden_id,
        "vehiculo_id": vehiculo_id,
        "tipo": tipo,
        "estado": "ABIERTA",
        "descripcion": descripcion,
        "km_entrada": km_entrada,
        "km_salida": None,
        "taller": taller,
        "fecha_programada": fecha_programada.isoformat(),
        "fecha_cierre": None,
        "costo_total": None,
        "orden_madre_id": None,
        "repuestos_estimados": [r.model_dump() for r in repuestos_estimados],
        "repuestos_consumidos": [],
    }

    if retirar_vehiculo:
        # La orden y el retiro del vehículo son dos entidades de negocio
        # distintas mutadas por la misma operación — se envuelven en una
        # transacción para que no quede una orden creada con el vehículo
        # todavía HABILITADO (o viceversa) si algo falla a mitad de camino.
        await with_transaction(
            get_mongo_client(),
            lambda session: _crear_orden_con_retiro(db, orden, actor_id=actor_id, actor_rol=actor_rol, session=session),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_REGISTRO,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"vehiculo_id": vehiculo_id, "tipo": tipo},
        )
        await db.ordenes.insert_one(orden)

    if vehiculo.get("propietario_id"):
        await dispatcher.notify_user(
            vehiculo["propietario_id"], "ORDEN_MANTENIMIENTO_REGISTRADA", {"orden_id": orden_id, "tipo": tipo}
        )

    return orden


async def _crear_orden_con_retiro(
    db: AsyncIOMotorDatabase, orden: dict, *, actor_id: str, actor_rol: str, session
) -> None:
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_REGISTRO,
        entidad="ordenes",
        entidad_id=orden["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"vehiculo_id": orden["vehiculo_id"], "tipo": orden["tipo"]},
        session=session,
    )
    await db.ordenes.insert_one(orden, session=session)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_RETIRO,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": f"orden {orden['_id']}"},
        session=session,
    )
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"]},
        {"$set": {"estado_habilitacion": "RETIRADO_DE_SERVICIO"}},
        session=session,
    )


async def marcar_en_taller(db: AsyncIOMotorDatabase, *, orden_id: str) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "ABIERTA":
        raise OrdenEstadoInvalidoError("ABIERTA")

    await db.ordenes.update_one({"_id": orden_id}, {"$set": {"estado": "EN_TALLER"}})
    orden["estado"] = "EN_TALLER"
    return orden


async def listar_ordenes(
    db: AsyncIOMotorDatabase,
    *,
    estado: str | None = None,
    vehiculo_id: str | None = None,
    placa: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if vehiculo_id:
        filtro["vehiculo_id"] = vehiculo_id
    if placa:
        vehiculos = await db.vehiculos.find({"placa": {"$regex": placa, "$options": "i"}}, {"_id": 1}).to_list(
            length=200
        )
        ids = [v["_id"] for v in vehiculos]
        filtro["vehiculo_id"] = {"$in": ids} if ids else "__ninguno__"
    total = await db.ordenes.count_documents(filtro)
    items = (
        await db.ordenes.find(filtro)
        .sort("fecha_programada", 1)
        .skip(offset)
        .limit(limit)
        .to_list(length=limit)
    )
    return items, total


async def cerrar_orden(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    orden_id: str,
    body: schemas.OrdenCerrarRequest,
) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "EN_TALLER":
        raise OrdenEstadoInvalidoError("EN_TALLER")
    # A3: kilometraje de salida menor al de entrada requiere ajuste
    # justificado explícito, registrado en la bitácora (no silencioso).
    if body.km_salida < orden["km_entrada"] and not body.ajuste_justificado:
        raise KmSalidaMenorError()

    ahora = datetime.now(UTC)

    if body.habilitar_vehiculo:
        orden_actualizada = await with_transaction(
            get_mongo_client(),
            lambda session: _cerrar_orden_con_habilitacion(
                db, orden, body=body, actor_id=actor_id, actor_rol=actor_rol, ahora=ahora, session=session
            ),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"costo_total": body.costo_total},
        )
        await db.ordenes.update_one(
            {"_id": orden_id},
            {
                "$set": {
                    "estado": "CERRADA",
                    "trabajos_realizados": body.trabajos_realizados,
                    "repuestos_consumidos": [r.model_dump() for r in body.repuestos_consumidos],
                    "costo_total": body.costo_total,
                    "horas_taller": body.horas_taller,
                    "km_salida": body.km_salida,
                    "fecha_cierre": ahora,
                }
            },
        )
        orden_actualizada = dict(orden)
        orden_actualizada.update(
            estado="CERRADA",
            trabajos_realizados=body.trabajos_realizados,
            repuestos_consumidos=[r.model_dump() for r in body.repuestos_consumidos],
            costo_total=body.costo_total,
            horas_taller=body.horas_taller,
            km_salida=body.km_salida,
            fecha_cierre=ahora,
        )

    if body.ajuste_justificado and body.km_salida < orden["km_entrada"]:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
            entidad="vehiculos",
            entidad_id=orden["vehiculo_id"],
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"ajuste_km": body.km_salida, "motivo": body.motivo_ajuste},
        )

    vehiculo = await db.vehiculos.find_one({"_id": orden["vehiculo_id"]})
    if vehiculo and vehiculo.get("propietario_id"):
        await dispatcher.notify_user(
            vehiculo["propietario_id"],
            "ORDEN_MANTENIMIENTO_CERRADA",
            {"orden_id": orden_id, "costo_total": body.costo_total},
        )

    return orden_actualizada


async def _cerrar_orden_con_habilitacion(
    db: AsyncIOMotorDatabase,
    orden: dict,
    *,
    body: schemas.OrdenCerrarRequest,
    actor_id: str,
    actor_rol: str,
    ahora: datetime,
    session,
) -> dict:
    orden_id = orden["_id"]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_CIERRE,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"costo_total": body.costo_total},
        session=session,
    )
    await db.ordenes.update_one(
        {"_id": orden_id},
        {
            "$set": {
                "estado": "CERRADA",
                "trabajos_realizados": body.trabajos_realizados,
                "repuestos_consumidos": [r.model_dump() for r in body.repuestos_consumidos],
                "costo_total": body.costo_total,
                "horas_taller": body.horas_taller,
                "km_salida": body.km_salida,
                "fecha_cierre": ahora,
            }
        },
        session=session,
    )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_HABILITACION,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"orden_id": orden_id},
        session=session,
    )
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"]},
        {"$set": {"estado_habilitacion": "HABILITADO"}},
        session=session,
    )

    resultado = dict(orden)
    resultado.update(
        estado="CERRADA",
        trabajos_realizados=body.trabajos_realizados,
        repuestos_consumidos=[r.model_dump() for r in body.repuestos_consumidos],
        costo_total=body.costo_total,
        horas_taller=body.horas_taller,
        km_salida=body.km_salida,
        fecha_cierre=ahora,
    )
    return resultado


async def anular_orden(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, orden_id: str, motivo: str) -> dict:
    orden = await db.ordenes.find_one({"_id": orden_id})
    if orden is None:
        raise OrdenNoEncontradaError()
    if orden["estado"] != "ABIERTA":
        raise OrdenEstadoInvalidoError("ABIERTA")

    vehiculo = await db.vehiculos.find_one({"_id": orden["vehiculo_id"]})
    debe_reabilitar = bool(vehiculo) and vehiculo.get("estado_habilitacion") == "RETIRADO_DE_SERVICIO"

    if debe_reabilitar:
        orden_actualizada = await with_transaction(
            get_mongo_client(),
            lambda session: _anular_orden_con_rehabilitacion(
                db, orden, motivo=motivo, actor_id=actor_id, actor_rol=actor_rol, session=session
            ),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.ORDEN_MANTENIMIENTO_ANULACION,
            entidad="ordenes",
            entidad_id=orden_id,
            resultado=ResultadoAuditoria.OK,
            datos_posteriores={"motivo": motivo},
        )
        await db.ordenes.update_one({"_id": orden_id}, {"$set": {"estado": "ANULADA", "motivo_anulacion": motivo}})
        orden_actualizada = dict(orden)
        orden_actualizada.update(estado="ANULADA")

    return orden_actualizada


async def _anular_orden_con_rehabilitacion(
    db: AsyncIOMotorDatabase, orden: dict, *, motivo: str, actor_id: str, actor_rol: str, session
) -> dict:
    orden_id = orden["_id"]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.ORDEN_MANTENIMIENTO_ANULACION,
        entidad="ordenes",
        entidad_id=orden_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": motivo},
        session=session,
    )
    await db.ordenes.update_one(
        {"_id": orden_id}, {"$set": {"estado": "ANULADA", "motivo_anulacion": motivo}}, session=session
    )

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.VEHICULO_HABILITACION,
        entidad="vehiculos",
        entidad_id=orden["vehiculo_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motivo": f"orden {orden_id} anulada"},
        session=session,
    )
    await db.vehiculos.update_one(
        {"_id": orden["vehiculo_id"]}, {"$set": {"estado_habilitacion": "HABILITADO"}}, session=session
    )

    resultado = dict(orden)
    resultado.update(estado="ANULADA")
    return resultado


async def listar_vehiculos_retirados(db: AsyncIOMotorDatabase) -> list[dict]:
    """Panel táctico -- CU-T04/OT7.1, informe simple (MongoDB):
    vehículos `RETIRADO_DE_SERVICIO` y la orden abierta que los retiene."""
    resultado: list[dict] = []
    async for vehiculo in db.vehiculos.find({"estado_habilitacion": "RETIRADO_DE_SERVICIO"}):
        orden = await db.ordenes.find_one(
            {"vehiculo_id": vehiculo["_id"], "estado": {"$in": ["ABIERTA", "EN_TALLER"]}},
            sort=[("fecha_programada", 1)],
        )
        resultado.append(
            {
                "vehiculo_id": vehiculo["_id"],
                "placa": vehiculo["placa"],
                "orden_id": orden["_id"] if orden else None,
                "orden_estado": orden["estado"] if orden else None,
                "fecha_programada": orden["fecha_programada"] if orden else None,
            }
        )
    return resultado


def obtener_cumplimiento_plan_preventivo() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T04/OT7.1."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_cumplimiento_plan_preventivo")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["periodo"])


async def obtener_costo_mantenimiento_top(db: AsyncIOMotorDatabase, *, top: int = 5) -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- CU-T11/OT7.2.

    El snapshot trae una fila por vehículo x periodo (mes); para el ranking
    del dashboard se acumula por vehículo (todos los periodos publicados) y
    se toman los `top` de mayor costo. `rpt_costo_mantenimiento_vehiculo` no
    tiene la placa (solo `vehiculo_id`, dimensión Gold) -- se resuelve acá
    mismo con un solo `$in` a Mongo, igual patrón que `obtener_placas_vehiculos`."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_costo_mantenimiento_vehiculo")
    finally:
        client.close()

    acumulado: dict[str, dict] = {}
    for fila in filas:
        acc = acumulado.setdefault(
            fila["vehiculo_id"], {"vehiculo_id": fila["vehiculo_id"], "costo_total": 0.0, "total_ordenes": 0}
        )
        acc["costo_total"] += fila["costo_total"]
        acc["total_ordenes"] += fila["total_ordenes"]

    resultado = sorted(acumulado.values(), key=lambda f: f["costo_total"], reverse=True)[:top]
    placas = await obtener_placas_vehiculos(db, {f["vehiculo_id"] for f in resultado})
    for fila in resultado:
        fila["vehiculo_placa"] = placas.get(fila["vehiculo_id"])
        fila["periodo"] = "acumulado"
    return resultado


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Estado y Costo de Flota
# (OE2b, nivel_estrategico.md §3.2.b, patrón Z)
# ---------------------------------------------------------------------------


async def obtener_panel_estado_costo_flota(
    db: AsyncIOMotorDatabase, *, meses: int = 12, top: int = 10
) -> dict:
    """Segunda capa de agregación sobre `rpt_cumplimiento_plan_preventivo` +
    `rpt_costo_mantenimiento_vehiculo`, sin tabla nueva.

    Las 2 fuentes ya traen `periodo` (mes) dentro del último snapshot, así
    que la tendencia extendida sale del propio `fetch_latest_snapshot` sin
    necesitar historial de cortes -- ver `core/agregacion_estrategica`, caso 1.

    **`km_recorridos` va siempre en `None`, a propósito.** La spec pide una
    tabla de "vehículos candidatos a reemplazo (costo vs. km recorridos)",
    pero el kilometraje no existe en ninguna de las 2 tablas `rpt_*` ni en
    ninguna otra vista publicada del nivel táctico. Los únicos km del sistema
    viven en `ordenes.km_entrada`/`km_salida` (Mongo), y la Sección 2 de la
    spec estratégica prohíbe explícitamente consultar Mongo para un informe
    de este nivel. Se declara `km_disponible=false` en metadata en vez de
    inventar un proxy -- mismo criterio que el gap de zona.

    El único acceso a Mongo de esta función resuelve la **placa** de cada
    vehículo del ranking (dato descriptivo, no una métrica), exactamente el
    mismo patrón ya aceptado en `obtener_costo_mantenimiento_top` del nivel
    táctico.
    """
    client = get_clickhouse_client()
    try:
        preventivo = fetch_latest_snapshot(client, "rpt_cumplimiento_plan_preventivo")
        costos = fetch_latest_snapshot(client, "rpt_costo_mantenimiento_vehiculo")
    finally:
        client.close()

    periodos = ultimos_periodos([f["periodo"] for f in preventivo] + [f["periodo"] for f in costos], meses)
    periodos_set = set(periodos)

    por_periodo_prev = agrupar([f for f in preventivo if f["periodo"] in periodos_set], "periodo")
    tendencia_preventivo = [
        {
            "periodo": periodo,
            "pct_cumplimiento": promedio_ponderado(por_periodo_prev[periodo], "pct_cumplimiento", "total_ordenes")
            or 0.0,
            "total_ordenes": sum(f["total_ordenes"] for f in por_periodo_prev[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_prev
    ]

    por_periodo_costo = agrupar([f for f in costos if f["periodo"] in periodos_set], "periodo")
    tendencia_costo = [
        {
            "periodo": periodo,
            "costo_total": round(sum(f["costo_total"] for f in por_periodo_costo[periodo]), 2),
            "total_ordenes": sum(f["total_ordenes"] for f in por_periodo_costo[periodo]),
        }
        for periodo in periodos
        if periodo in por_periodo_costo
    ]

    pct_actual = tendencia_preventivo[-1]["pct_cumplimiento"] if tendencia_preventivo else None
    pct_previo = tendencia_preventivo[-2]["pct_cumplimiento"] if len(tendencia_preventivo) > 1 else None
    costo_actual = tendencia_costo[-1]["costo_total"] if tendencia_costo else None
    costo_previo = tendencia_costo[-2]["costo_total"] if len(tendencia_costo) > 1 else None

    acumulado: dict[str, dict] = {}
    for fila in costos:
        if fila["periodo"] not in periodos_set:
            continue
        acc = acumulado.setdefault(
            fila["vehiculo_id"],
            {"vehiculo_id": fila["vehiculo_id"], "costo_total": 0.0, "total_ordenes": 0, "periodos": 0},
        )
        acc["costo_total"] += fila["costo_total"]
        acc["total_ordenes"] += fila["total_ordenes"]
        acc["periodos"] += 1

    candidatos = sorted(acumulado.values(), key=lambda f: f["costo_total"], reverse=True)[:top]
    placas = await obtener_placas_vehiculos(db, {f["vehiculo_id"] for f in candidatos})
    for fila in candidatos:
        fila["costo_total"] = round(fila["costo_total"], 2)
        fila["vehiculo_placa"] = placas.get(fila["vehiculo_id"])
        fila["costo_promedio_mes"] = round(fila["costo_total"] / fila["periodos"], 2) if fila["periodos"] else None
        fila["km_recorridos"] = None  # ver docstring: no existe en ninguna rpt_*

    return {
        "kpis": {
            "pct_cumplimiento_preventivo": pct_actual,
            "variacion_cumplimiento_pct": variacion_pct(pct_actual, pct_previo),
            "costo_mantenimiento_periodo": costo_actual,
            "variacion_costo_pct": variacion_pct(costo_actual, costo_previo),
            "costo_acumulado": round(sum(f["costo_total"] for f in acumulado.values()), 2) if acumulado else None,
        },
        "tendencia_preventivo": tendencia_preventivo,
        "tendencia_costo": tendencia_costo,
        "candidatos_reemplazo": candidatos,
        "metadata": {
            "meses": meses,
            "km_disponible": False,
            "fuentes": ["rpt_cumplimiento_plan_preventivo", "rpt_costo_mantenimiento_vehiculo"],
        },
    }
