"""Cumplimiento — control de vigencia documental (job diario descrito en
operativo_cumplimiento.md, técnicamente CU-T10 pero especificado inline en
ese archivo) + verificación de renovación de documentos (mismo patrón de
verificación que CU-O03).

Modelo de banderas (ítem 7 del plan, ya resuelto): una bandera booleana
`cumplimiento_ok` por conductor (en `usuario.conductor.cumplimiento_ok`) y
otra por vehículo (`vehiculo.cumplimiento_ok`), cada una con su propio
`cumplimiento_motivo`. Ausencia del campo se trata como cumplimiento OK — un
conductor/vehículo recién aprobado por Captación no tiene el campo todavía y
es, correctamente, cumplido hasta que este job diga lo contrario. Esta
bandera es independiente de `vehiculo.estado_habilitacion` (esa es la
bandera de Mantenimiento, CU-O12/O13).
"""

from datetime import date, datetime, timedelta, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.agregacion_estrategica import agrupar, promedio_ponderado, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, fetch_snapshot_history, get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.db_transaction import with_transaction
from src.core.exceptions import DomainError
from src.archivos import service as archivos_service
from src.core.notifications import NotificationDispatcher

_UMBRALES_NOTIFICACION = frozenset({30, 15, 7, 1})


class DocumentoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="DOCUMENTO_NO_ENCONTRADO", message="El documento no existe", status_code=404)


class SinRenovacionPendienteError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="SIN_RENOVACION_PENDIENTE", message="El documento no tiene una renovación pendiente", status_code=409
        )


class DocumentoNoPropioError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="DOCUMENTO_NO_PROPIO",
            message="Este documento no pertenece a tu cuenta ni a un vehículo tuyo",
            status_code=403,
        )


class ArchivoNoValidoParaRenovacionError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            code="ARCHIVO_NO_VALIDO_PARA_RENOVACION",
            message="El archivo no es tuyo o no se subió para una renovación de documento",
            status_code=422,
        )


def _parse_fecha(valor) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


async def _usuario_a_notificar(db: AsyncIOMotorDatabase, propietario_tipo: str, propietario_id: str) -> str | None:
    if propietario_tipo == "CONDUCTOR":
        return propietario_id
    vehiculo = await db.vehiculos.find_one({"_id": propietario_id})
    return vehiculo.get("propietario_id") if vehiculo else None


async def _marcar_vencido(db: AsyncIOMotorDatabase, doc: dict) -> bool:
    propietario_tipo = doc["propietario_tipo"]
    propietario_id = doc["propietario_id"]
    coleccion = db.usuarios if propietario_tipo == "CONDUCTOR" else db.vehiculos

    actual = await coleccion.find_one({"_id": propietario_id})
    if actual is None:
        return False

    if propietario_tipo == "CONDUCTOR":
        flag_actual = (actual.get("conductor") or {}).get("cumplimiento_ok")
    else:
        flag_actual = actual.get("cumplimiento_ok")
    if flag_actual is False:
        return False  # ya estaba en rojo — no repetir el efecto ni la auditoría cada día

    motivo = f"documento {doc['tipo']} vencido"

    # Write-ahead antes de bajar la bandera — es un cambio de estado que
    # bloquea el inicio de turno del conductor/vehículo.
    await write_audit_event(
        db,
        actor_id=None,
        rol=None,
        accion=AccionAuditoria.CUMPLIMIENTO_BANDERA_CAMBIO,
        entidad=propietario_tipo.lower(),
        entidad_id=propietario_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"cumplimiento_ok": False, "motivo": motivo},
    )

    if propietario_tipo == "CONDUCTOR":
        await db.usuarios.update_one(
            {"_id": propietario_id},
            {"$set": {"conductor.cumplimiento_ok": False, "conductor.cumplimiento_motivo": motivo}},
        )
    else:
        await db.vehiculos.update_one(
            {"_id": propietario_id}, {"$set": {"cumplimiento_ok": False, "cumplimiento_motivo": motivo}}
        )

    return True


async def ejecutar_control_vigencia_documental(db: AsyncIOMotorDatabase, dispatcher: NotificationDispatcher) -> dict:
    # date.today() usa la zona horaria local del sistema/contenedor; la
    # arquitectura exige timestamps en UTC (línea 122) precisamente para
    # evitar que el mismo cálculo dé un día distinto según dónde corra el
    # proceso. `_parse_fecha` también asume fechas en UTC.
    hoy = datetime.now(UTC).date()
    revisados = 0
    por_vencer_notificados = 0
    vencidos_nuevos = 0

    async for doc in db.documentos.find({"fecha_vencimiento": {"$ne": None}}):
        fecha_vto = _parse_fecha(doc.get("fecha_vencimiento"))
        if fecha_vto is None:
            continue
        revisados += 1
        dias = (fecha_vto - hoy).days

        if dias < 0:
            if await _marcar_vencido(db, doc):
                vencidos_nuevos += 1
                usuario_id = await _usuario_a_notificar(db, doc["propietario_tipo"], doc["propietario_id"])
                if usuario_id:
                    await dispatcher.notify_user(
                        usuario_id, "DOCUMENTO_VENCIDO", {"documento_id": doc["_id"], "tipo": doc["tipo"]}
                    )
        elif dias in _UMBRALES_NOTIFICACION:
            usuario_id = await _usuario_a_notificar(db, doc["propietario_tipo"], doc["propietario_id"])
            if usuario_id:
                por_vencer_notificados += 1
                await dispatcher.notify_user(
                    usuario_id, "DOCUMENTO_POR_VENCER", {"documento_id": doc["_id"], "dias_para_vencer": dias}
                )

    return {
        "revisados": revisados,
        "por_vencer_notificados": por_vencer_notificados,
        "vencidos_nuevos": vencidos_nuevos,
    }


async def listar_renovaciones_pendientes(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.documentos.find({"renovacion_pendiente": {"$ne": None}}).to_list(length=200)


async def resolver_nombres_propietarios(db: AsyncIOMotorDatabase, documentos: list[dict]) -> dict[str, str]:
    """Resuelve `propietario_id` -> nombre legible para la bandeja de
    renovaciones pendientes: `nombre` (de `usuarios`) cuando
    `propietario_tipo == "CONDUCTOR"`, `placa` (de `vehiculos`) cuando es
    `"VEHICULO"`. Batch `$in` por colección, mismo criterio que
    `captacion.service.enriquecer_con_usuario_nombre`. Se indexa solo por
    `propietario_id` (no por tupla tipo+id) porque ambos ids son UUIDs
    generados independientemente — la colisión entre un usuario_id y un
    vehiculo_id es, en la práctica, imposible."""
    ids_conductor = {d["propietario_id"] for d in documentos if d["propietario_tipo"] == "CONDUCTOR"}
    ids_vehiculo = {d["propietario_id"] for d in documentos if d["propietario_tipo"] == "VEHICULO"}

    nombres: dict[str, str] = {}
    if ids_conductor:
        usuarios = await db.usuarios.find({"_id": {"$in": list(ids_conductor)}}).to_list(length=len(ids_conductor))
        nombres.update({u["_id"]: u["nombre"] for u in usuarios})
    if ids_vehiculo:
        vehiculos = await db.vehiculos.find({"_id": {"$in": list(ids_vehiculo)}}).to_list(length=len(ids_vehiculo))
        nombres.update({v["_id"]: v["placa"] for v in vehiculos})
    return nombres


async def _ids_vehiculos_de(db: AsyncIOMotorDatabase, conductor_id: str) -> list[str]:
    vehiculos = await db.vehiculos.find({"propietario_id": conductor_id}, {"_id": 1}).to_list(length=50)
    return [v["_id"] for v in vehiculos]


async def listar_mis_documentos(db: AsyncIOMotorDatabase, *, conductor_id: str) -> list[dict]:
    """Autoservicio del conductor -- cierra el gap real: hasta ahora ningún
    endpoint le dejaba ver sus propios documentos, así que la bandeja de
    renovaciones pendientes (`listar_renovaciones_pendientes`) estaba
    condenada a quedar vacía para siempre: nadie tenía cómo generar una
    renovación pendiente. Mismo criterio de propiedad que `_usuario_a_notificar`
    (documento directo del conductor, o de un vehículo suyo), en la
    dirección inversa."""
    ids_vehiculos = await _ids_vehiculos_de(db, conductor_id)
    filtro = {
        "$or": [
            {"propietario_tipo": "CONDUCTOR", "propietario_id": conductor_id},
            {"propietario_tipo": "VEHICULO", "propietario_id": {"$in": ids_vehiculos}},
        ]
    }
    documentos = await db.documentos.find(filtro).sort("fecha_vencimiento", 1).to_list(length=100)
    hoy = date.today()
    for doc in documentos:
        vencimiento = doc.get("fecha_vencimiento")
        doc["dias_restantes"] = (date.fromisoformat(vencimiento) - hoy).days if vencimiento else None
    return documentos


async def subir_renovacion(
    db: AsyncIOMotorDatabase, *, actor_id: str, documento_id: str, archivo_id: str, fecha_vencimiento: date
) -> dict:
    documento = await db.documentos.find_one({"_id": documento_id})
    if documento is None:
        raise DocumentoNoEncontradoError()

    # El documento tiene que ser del propio actor (directo, o de un vehículo
    # suyo) -- antes de este cierre de gap, este endpoint no verificaba NADA,
    # ni siquiera exigía sesión: cualquiera con un `documento_id` podía
    # cargarle una renovación falsa a un documento ajeno.
    dueno_real = await _usuario_a_notificar(db, documento["propietario_tipo"], documento["propietario_id"])
    if dueno_real != actor_id:
        raise DocumentoNoPropioError()

    # El archivo tiene que ser del propio actor y haberse subido para ESTE
    # propósito -- mismo criterio ya usado en `perfil.service.editar_foto_perfil`
    # para que nadie "adopte" como renovación un archivo ajeno o uno subido
    # para otro contexto (ej. evidencia de una falla).
    archivo = await archivos_service.obtener_archivo(db, archivo_id=archivo_id)
    if archivo["propietario_id"] != actor_id or archivo["contexto"] != "documento_renovacion":
        raise ArchivoNoValidoParaRenovacionError()

    pendiente = {
        "url_objeto": archivo["_id"],
        "hash_archivo": archivo["hash_sha256"],
        "fecha_vencimiento": fecha_vencimiento.isoformat(),
    }
    await db.documentos.update_one({"_id": documento_id}, {"$set": {"renovacion_pendiente": pendiente}})
    documento["renovacion_pendiente"] = pendiente
    return documento


async def verificar_renovacion(
    db: AsyncIOMotorDatabase,
    dispatcher: NotificationDispatcher,
    *,
    actor_id: str,
    actor_rol: str,
    documento_id: str,
    aprobar: bool,
    motivo: str | None,
) -> dict:
    documento = await db.documentos.find_one({"_id": documento_id})
    if documento is None:
        raise DocumentoNoEncontradoError()
    pendiente = documento.get("renovacion_pendiente")
    if not pendiente:
        raise SinRenovacionPendienteError()

    if aprobar:
        # Toca 2 entidades (el documento y la bandera del conductor/vehículo
        # propietario) — transacción, igual que Mantenimiento y Captación.
        resultado = await with_transaction(
            get_mongo_client(),
            lambda session: _aprobar_renovacion(
                db, documento, pendiente, actor_id=actor_id, actor_rol=actor_rol, session=session
            ),
        )
    else:
        await write_audit_event(
            db,
            actor_id=actor_id,
            rol=actor_rol,
            accion=AccionAuditoria.CUMPLIMIENTO_BANDERA_CAMBIO,
            entidad="documentos",
            entidad_id=documento_id,
            resultado=ResultadoAuditoria.DENEGADO,
            datos_posteriores={"motivo": motivo},
        )
        await db.documentos.update_one({"_id": documento_id}, {"$unset": {"renovacion_pendiente": ""}})
        resultado = dict(documento)
        resultado.pop("renovacion_pendiente", None)

    usuario_id = await _usuario_a_notificar(db, documento["propietario_tipo"], documento["propietario_id"])
    if usuario_id:
        payload = {"documento_id": documento_id, "aprobado": aprobar, "motivo": motivo}
        await dispatcher.notify_user(usuario_id, "RENOVACION_DOCUMENTO_DECISION", payload)

    return resultado


async def _aprobar_renovacion(
    db: AsyncIOMotorDatabase, documento: dict, pendiente: dict, *, actor_id: str, actor_rol: str, session
) -> dict:
    documento_id = documento["_id"]
    propietario_tipo = documento["propietario_tipo"]
    propietario_id = documento["propietario_id"]

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.CUMPLIMIENTO_BANDERA_CAMBIO,
        entidad="documentos",
        entidad_id=documento_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"fecha_vencimiento": pendiente["fecha_vencimiento"]},
        session=session,
    )
    await db.documentos.update_one(
        {"_id": documento_id},
        {
            "$set": {
                "url_objeto": pendiente["url_objeto"],
                "hash_archivo": pendiente["hash_archivo"],
                "fecha_vencimiento": pendiente["fecha_vencimiento"],
                "estado_verificacion": "CONFORME",
                "verificador_id": actor_id,
                "fecha_verificacion": datetime.now(UTC),
            },
            "$unset": {"renovacion_pendiente": ""},
        },
        session=session,
    )

    if propietario_tipo == "CONDUCTOR":
        await db.usuarios.update_one(
            {"_id": propietario_id},
            {"$set": {"conductor.cumplimiento_ok": True, "conductor.cumplimiento_motivo": None}},
            session=session,
        )
    else:
        await db.vehiculos.update_one(
            {"_id": propietario_id}, {"$set": {"cumplimiento_ok": True, "cumplimiento_motivo": None}}, session=session
        )

    resultado = dict(documento)
    resultado.update(fecha_vencimiento=pendiente["fecha_vencimiento"], estado_verificacion="CONFORME")
    resultado.pop("renovacion_pendiente", None)
    return resultado


async def listar_documentos_vencidos_y_por_vencer(db: AsyncIOMotorDatabase, *, dias: int = 30) -> list[dict]:
    """Panel táctico de Vigencia Documental -- CU-T10/OT6.1, informe simple (MongoDB).

    Documentos ya vencidos o que vencen dentro de `dias` (default 30) a
    partir de hoy, sin importar el estado de verificación -- el supervisor
    necesita ver tanto los bloqueados como los que siguen conformes pero
    están por caducar."""
    limite = date.today() + timedelta(days=dias)
    cursor = db.documentos.find({"fecha_vencimiento": {"$lte": limite.isoformat()}}).sort("fecha_vencimiento", 1)
    documentos = await cursor.to_list(length=500)
    nombres = await resolver_nombres_propietarios(db, documentos)
    hoy = date.today()
    for doc in documentos:
        doc["propietario_nombre"] = nombres.get(doc["propietario_id"])
        vencimiento = doc.get("fecha_vencimiento")
        doc["dias_restantes"] = (date.fromisoformat(vencimiento) - hoy).days if vencimiento else None
    return documentos


def obtener_documentacion_vigente() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico -- último corte publicado, por tipo."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_documentacion_vigente")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["tipo"])


def obtener_documentacion_tendencia(*, dias: int = 30) -> list[dict]:
    """Tendencia mensual de documentación vigente -- CU-T10/OT6.1.

    `rpt_documentacion_vigente` es MergeTree (no Replacing) y conserva un
    corte por cada `fecha_datos` en que corrió `dag_cumplimiento_gold`, así
    que la tendencia se lee directo del historial ya publicado -- sin tabla
    nueva, sin cambios al DAG."""
    client = get_clickhouse_client()
    try:
        filas = fetch_snapshot_history(client, "rpt_documentacion_vigente", limite_dias=dias)
    finally:
        client.close()
    return sorted(filas, key=lambda f: (f["fecha_datos"], f["tipo"]))


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Cumplimiento Normativo
# (OE6a, nivel_estrategico.md §3.6.a, patrón Z)
# ---------------------------------------------------------------------------


def obtener_panel_cumplimiento_normativo(*, cortes: int = 12) -> dict:
    """Segunda capa de agregación sobre `rpt_documentacion_vigente`, sin tabla nueva.

    La tabla no tiene dimensión de periodo propia (es un corte por corrida de
    `dag_cumplimiento_gold`), así que la tendencia sale de
    `fetch_snapshot_history` sobre `fecha_datos` -- caso 2 de
    `core/agregacion_estrategica`, el mismo mecanismo que ya usa la tendencia
    del panel táctico de Documentación.

    `documentos_vencidos` se deriva del propio snapshot
    (`total_registros * (1 - pct_vigente)`, redondeado): la tabla publica el
    porcentaje y el total, no el conteo de vencidos -- calcularlo acá es
    aritmética sobre el dato publicado, no una consulta nueva a Mongo.
    """
    client = get_clickhouse_client()
    try:
        actual = fetch_latest_snapshot(client, "rpt_documentacion_vigente")
        historial = fetch_snapshot_history(client, "rpt_documentacion_vigente", limite_dias=cortes)
    finally:
        client.close()

    def _vencidos(filas: list[dict]) -> int:
        return round(sum(f["total_registros"] * (1 - f["pct_vigente"]) for f in filas))

    tendencia = [
        {
            "periodo": str(fecha),
            "pct_vigente": promedio_ponderado(filas, "pct_vigente", "total_registros") or 0.0,
            "total_registros": sum(f["total_registros"] for f in filas),
            "documentos_vencidos": _vencidos(filas),
        }
        for fecha, filas in sorted(agrupar(historial, "fecha_datos").items())
    ]

    tipos = sorted(
        (
            {
                "tipo": f["tipo"],
                "pct_vigente": f["pct_vigente"],
                "total_registros": f["total_registros"],
                "documentos_vencidos": round(f["total_registros"] * (1 - f["pct_vigente"])),
            }
            for f in actual
        ),
        key=lambda f: f["pct_vigente"],
    )

    pct_actual = promedio_ponderado(actual, "pct_vigente", "total_registros")
    pct_previo = tendencia[-2]["pct_vigente"] if len(tendencia) > 1 else None
    # Tier 1, punto 6 (H-T5): `pct_vigente` es un promedio ponderado por
    # `total_registros` -- el n real del periodo anterior es ese peso.
    registros_previos_vigencia = tendencia[-2]["total_registros"] if len(tendencia) > 1 else None

    return {
        "kpis": {
            "pct_vigente": pct_actual,
            "variacion_vigencia_pct": variacion_pct(pct_actual, pct_previo),
            "documentos_vencidos": _vencidos(actual),
            "tipo_mas_expuesto": tipos[0]["tipo"] if tipos else None,
        },
        "tendencia_vigencia": tendencia,
        "tipos": tipos,
        "metadata": {
            "cortes": cortes,
            "fuentes": ["rpt_documentacion_vigente"],
            "registros_previos": {"variacion_vigencia_pct": registros_previos_vigencia},
        },
    }
