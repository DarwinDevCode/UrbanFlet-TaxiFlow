"""Respaldos y Continuidad — Módulo 7 de admin_sistema
(specs/specs-administrativas/admin_sistema.md).

**7.1 (respaldos) -- decisión de arquitectura confirmada explícitamente por
el usuario antes de construir** (ver PLAN_ADMIN_SISTEMA.md §18): la spec
sugiere `mongodump`/`clickhouse-client` como herramientas -- verificado
que **ninguna de las dos está instalada** en la imagen del backend
(`python:3.11-slim`, sin `mongodb-database-tools` ni `clickhouse-client`) y
que agregarlas requeriría reconstruir la imagen. Se optó por exportación
vía los drivers que el backend YA usa en producción (`motor` para Mongo,
`clickhouse_connect` para ClickHouse) en vez de instalar binarios nuevos
solo para esta función -- el respaldo resultante es real y restaurable,
solo que con un formato propio (JSONL para Mongo, pickle para ClickHouse)
en vez del formato binario nativo de `mongodump`.

Alcance de qué se respalda (decisión documentada, no un olvido):
- **Mongo**: TODAS las colecciones de negocio real, incluida `bitacora`
  (auditoría permanente, perderla sería grave) y `posiciones` (TTL de 7
  días propio, pero no hay razón para excluirla de un respaldo puntual).
  Se excluyen únicamente las colecciones propias de este mismo módulo
  (`respaldos`, `plan_dr`, `simulacros_dr`, `restauraciones`) -- haría un
  respaldo de sus propios metadatos, sin valor.
- **ClickHouse**: solo las tablas `rpt_*` (capa de reporting que alimenta
  los 9 dashboards tácticos) + un puñado de tablas pequeñas de referencia
  (`dim_tiempo`, `dim_zona`, `corridas`, `alertas`). Se **excluyen**
  deliberadamente `bronze_*`/`fact_*`/`cuarentena_*` -- son capas
  intermedias del pipeline ETL, 100% re-derivables re-ejecutando los DAGs
  de Airflow contra Mongo/PocketBase (las fuentes de verdad reales, que sí
  se respaldan del lado de Mongo) -- en este entorno de desarrollo esas
  tablas ya suman más de 6 millones de filas (`bronze_pagos`,
  `bronze_viaje_historico_nyc`, etc., ver verificación real contra
  `system.tables` antes de construir), volumen que no aporta resiliencia
  real (no son la fuente de verdad) y sí multiplicaría el tiempo de
  respaldo sin necesidad.

La restauración de prueba **nunca** acepta un nombre de base de destino
del cliente -- siempre está hardcodeada a `urbanflet_restore_test`
(Mongo) / `urbanflet_gold_restore_test` (ClickHouse), nunca las bases
reales. Cifrado en reposo: **no implementado** en este entorno de
desarrollo -- documentado explícitamente en la UI, no simulado.
"""

import asyncio
import hashlib
import pickle
import uuid
from collections.abc import Coroutine
from datetime import datetime, UTC
from pathlib import Path

from bson import json_util
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.config import get_settings
from src.core.db_clickhouse import get_clickhouse_client
from src.core.db_mongo import get_mongo_client
from src.core.exceptions import DomainError

COLECCIONES_EXCLUIDAS_MONGO = frozenset({"respaldos", "plan_dr", "simulacros_dr", "restauraciones"})

# Tablas ClickHouse incluidas en el respaldo -- ver docstring del módulo
# para la razón de excluir bronze_*/fact_*/cuarentena_*.
_TABLAS_CLICKHOUSE_EXTRA = frozenset({"dim_tiempo", "dim_zona", "corridas", "alertas"})

MONGO_RESTORE_DB = "urbanflet_restore_test"
CLICKHOUSE_RESTORE_DB = "urbanflet_gold_restore_test"

DOMINIOS_DR = (
    "captacion", "operaciones_despacho", "flota", "mantenimiento", "finanzas", "cumplimiento", "plataforma"
)


# Referencia fuerte a las tareas de fondo (respaldo/restauración) mientras
# corren -- sin esto, `asyncio.create_task` no garantiza que la tarea
# sobreviva si nada más la referencia (el event loop puede recolectarla a
# medio correr, un gotcha real y documentado de `asyncio`).
_TAREAS_EN_FONDO: set[asyncio.Task] = set()


def lanzar_en_fondo(coro: Coroutine) -> asyncio.Task:
    tarea = asyncio.create_task(coro)
    _TAREAS_EN_FONDO.add(tarea)
    tarea.add_done_callback(_TAREAS_EN_FONDO.discard)
    return tarea


class RespaldoNoEncontradoError(DomainError):
    def __init__(self) -> None:
        super().__init__(code="RESPALDO_NO_ENCONTRADO", message="El respaldo no existe", status_code=404)


class RespaldoNoDisponibleError(DomainError):
    def __init__(self, estado: str) -> None:
        super().__init__(
            code="RESPALDO_NO_DISPONIBLE",
            message=f"El respaldo no está listo para esta operación (estado: {estado})",
            status_code=409,
        )


def _como_utc(dt: datetime) -> datetime:
    """Mongo (real o mongomock) devuelve `datetime` naive en UTC -- BSON no
    guarda tzinfo. Sin esto, restar contra un `datetime.now(UTC)` recién
    creado revienta con `TypeError: can't subtract offset-naive and
    offset-aware datetimes` (bug real, no solo de tests: pasaría igual
    contra el Mongo real de producción)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _ruta_respaldos() -> Path:
    ruta = Path(get_settings().respaldos_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def respaldo_a_salida(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "motor": doc["motor"],
        "estado": doc["estado"],
        "ts_inicio": doc["ts_inicio"],
        "ts_fin": doc.get("ts_fin"),
        "duracion_segundos": doc.get("duracion_segundos"),
        "tamano_bytes": doc.get("tamano_bytes"),
        "hash_sha256": doc.get("hash_sha256"),
        "colecciones": doc.get("colecciones"),
        "error_detalle": doc.get("error_detalle"),
        "disparado_por": doc["disparado_por"],
    }


async def disparar_respaldo(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str) -> list[dict]:
    ahora = datetime.now(UTC)
    docs = []
    for motor in ("mongo", "clickhouse"):
        doc = {
            "_id": str(uuid.uuid4()),
            "motor": motor,
            "estado": "en_progreso",
            "ts_inicio": ahora,
            "ts_fin": None,
            "duracion_segundos": None,
            "tamano_bytes": None,
            "hash_sha256": None,
            "colecciones": None,
            "error_detalle": None,
            "disparado_por": actor_id,
        }
        docs.append(doc)

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.RESPALDO_DISPARO,
        entidad="respaldos",
        entidad_id=",".join(d["_id"] for d in docs),
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"motores": ["mongo", "clickhouse"]},
    )
    await db.respaldos.insert_many(docs)
    return docs


async def ejecutar_respaldo_mongo(respaldo_id: str) -> None:
    """Corre fuera del ciclo de vida de la petición HTTP (tarea de fondo) --
    usa `get_mongo_client()` directo en vez del `db` inyectado por request,
    que ya no existe cuando esta corrutina sigue corriendo tras la
    respuesta 202."""
    db = get_mongo_client()[get_settings().mongo_db_name]
    ruta = _ruta_respaldos() / f"mongo_{respaldo_id}.jsonl"
    hasher = hashlib.sha256()
    colecciones_incluidas: list[str] = []

    try:
        nombres = [c for c in await db.list_collection_names() if c not in COLECCIONES_EXCLUIDAS_MONGO]
        with open(ruta, "wb") as f:
            for nombre in sorted(nombres):
                marcador = (json_util.dumps({"__coleccion__": nombre}) + "\n").encode("utf-8")
                f.write(marcador)
                hasher.update(marcador)
                total_coleccion = 0
                cursor = db[nombre].find(batch_size=2000)
                async for documento in cursor:
                    linea = (json_util.dumps(documento) + "\n").encode("utf-8")
                    f.write(linea)
                    hasher.update(linea)
                    total_coleccion += 1
                colecciones_incluidas.append(nombre)

        await _marcar_completado(respaldo_id, ruta, hasher.hexdigest(), colecciones_incluidas)
    except Exception as exc:  # noqa: BLE001 -- tarea de fondo: se persiste el error, no se relanza a nadie
        await _marcar_error(respaldo_id, str(exc)[:500])


async def ejecutar_respaldo_clickhouse(respaldo_id: str) -> None:
    ruta = _ruta_respaldos() / f"clickhouse_{respaldo_id}.pkl"
    try:
        client = get_clickhouse_client()
        tablas_rpt = [
            row[0]
            for row in client.query(
                "SELECT name FROM system.tables WHERE database = currentDatabase() AND name LIKE 'rpt\\_%'"
            ).result_rows
        ]
        tablas = sorted(set(tablas_rpt) | _TABLAS_CLICKHOUSE_EXTRA)

        contenido: dict[str, dict] = {}
        for tabla in tablas:
            try:
                resultado = client.query(f"SELECT * FROM {tabla}")
            except Exception:  # noqa: BLE001 -- tabla listada pero inexistente/vacía en este entorno: se omite
                continue
            contenido[tabla] = {"columnas": resultado.column_names, "filas": resultado.result_rows}

        with open(ruta, "wb") as f:
            pickle.dump(contenido, f)

        hasher = hashlib.sha256()
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(bloque)

        await _marcar_completado(respaldo_id, ruta, hasher.hexdigest(), sorted(contenido))
    except Exception as exc:  # noqa: BLE001 -- ver nota de ejecutar_respaldo_mongo
        await _marcar_error(respaldo_id, str(exc)[:500])


async def _marcar_completado(respaldo_id: str, ruta: Path, hash_sha256: str, incluidos: list[str]) -> None:
    db = get_mongo_client()[get_settings().mongo_db_name]
    doc = await db.respaldos.find_one({"_id": respaldo_id})
    ts_fin = datetime.now(UTC)
    duracion = (ts_fin - _como_utc(doc["ts_inicio"])).total_seconds()
    await db.respaldos.update_one(
        {"_id": respaldo_id},
        {
            "$set": {
                "estado": "completado",
                "ts_fin": ts_fin,
                "duracion_segundos": duracion,
                "tamano_bytes": ruta.stat().st_size,
                "hash_sha256": hash_sha256,
                "colecciones": incluidos,
                "ruta_archivo": str(ruta),
            }
        },
    )


async def _marcar_error(respaldo_id: str, detalle: str) -> None:
    db = get_mongo_client()[get_settings().mongo_db_name]
    await db.respaldos.update_one(
        {"_id": respaldo_id},
        {"$set": {"estado": "error", "ts_fin": datetime.now(UTC), "error_detalle": detalle}},
    )


async def listar_respaldos(db: AsyncIOMotorDatabase) -> list[dict]:
    docs = await db.respaldos.find().sort("ts_inicio", -1).to_list(length=100)
    return [respaldo_a_salida(d) for d in docs]


async def verificar_respaldo(db: AsyncIOMotorDatabase, respaldo_id: str) -> dict:
    doc = await db.respaldos.find_one({"_id": respaldo_id})
    if doc is None:
        raise RespaldoNoEncontradoError()
    if doc["estado"] != "completado":
        raise RespaldoNoDisponibleError(doc["estado"])

    ruta = Path(doc["ruta_archivo"])
    hasher = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(bloque)
    calculado = hasher.hexdigest()
    return {
        "id": respaldo_id,
        "integro": calculado == doc["hash_sha256"],
        "hash_esperado": doc["hash_sha256"],
        "hash_calculado": calculado,
    }


def restauracion_a_salida(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "respaldo_id": doc["respaldo_id"],
        "motor": doc["motor"],
        "estado": doc["estado"],
        "base_destino": doc["base_destino"],
        "ts_inicio": doc["ts_inicio"],
        "ts_fin": doc.get("ts_fin"),
        "duracion_segundos": doc.get("duracion_segundos"),
        "conteos": doc.get("conteos"),
        "error_detalle": doc.get("error_detalle"),
    }


async def restaurar_respaldo(db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, respaldo_id: str) -> dict:
    doc = await db.respaldos.find_one({"_id": respaldo_id})
    if doc is None:
        raise RespaldoNoEncontradoError()
    if doc["estado"] != "completado":
        raise RespaldoNoDisponibleError(doc["estado"])

    base_destino = MONGO_RESTORE_DB if doc["motor"] == "mongo" else CLICKHOUSE_RESTORE_DB
    ahora = datetime.now(UTC)
    restauracion = {
        "_id": str(uuid.uuid4()),
        "respaldo_id": respaldo_id,
        "motor": doc["motor"],
        "estado": "en_progreso",
        "base_destino": base_destino,
        "ts_inicio": ahora,
        "ts_fin": None,
        "duracion_segundos": None,
        "conteos": None,
        "error_detalle": None,
    }

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.RESPALDO_RESTAURACION_PRUEBA,
        entidad="respaldos",
        entidad_id=respaldo_id,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"base_destino": base_destino, "restauracion_id": restauracion["_id"]},
    )
    await db.restauraciones.insert_one(restauracion)
    return restauracion


async def ejecutar_restauracion_mongo(restauracion_id: str, ruta_archivo: str) -> None:
    client = get_mongo_client()
    destino = client[MONGO_RESTORE_DB]
    conteos: dict[str, int] = {}

    try:
        coleccion_actual: str | None = None
        lote: list[dict] = []

        async def _volcar_lote() -> None:
            nonlocal lote
            if lote and coleccion_actual:
                await destino[coleccion_actual].insert_many(lote, ordered=False)
                conteos[coleccion_actual] = conteos.get(coleccion_actual, 0) + len(lote)
            lote = []

        with open(ruta_archivo, "rb") as f:
            for linea in f:
                obj = json_util.loads(linea)
                if isinstance(obj, dict) and "__coleccion__" in obj:
                    await _volcar_lote()
                    coleccion_actual = obj["__coleccion__"]
                    await destino[coleccion_actual].delete_many({})
                    conteos.setdefault(coleccion_actual, 0)
                    continue
                lote.append(obj)
                if len(lote) >= 2000:
                    await _volcar_lote()
            await _volcar_lote()

        await _marcar_restauracion_completada(restauracion_id, conteos)
    except Exception as exc:  # noqa: BLE001 -- ver nota de ejecutar_respaldo_mongo
        await _marcar_restauracion_error(restauracion_id, str(exc)[:500])


async def ejecutar_restauracion_clickhouse(restauracion_id: str, ruta_archivo: str) -> None:
    conteos: dict[str, int] = {}
    try:
        # `use_database=False` en cada comando porque el SQL ya califica
        # `<base>.<tabla>` explícitamente -- evita cualquier ambigüedad
        # sobre en qué base corre el DDL, en vez de depender del atributo
        # `database` del cliente.
        cliente = get_clickhouse_client()
        cliente.command(f"CREATE DATABASE IF NOT EXISTS {CLICKHOUSE_RESTORE_DB}", use_database=False)

        with open(ruta_archivo, "rb") as f:
            contenido: dict[str, dict] = pickle.load(f)

        for tabla, datos in contenido.items():
            cliente.command(f"DROP TABLE IF EXISTS {CLICKHOUSE_RESTORE_DB}.{tabla}", use_database=False)
            cliente.command(
                f"CREATE TABLE {CLICKHOUSE_RESTORE_DB}.{tabla} AS urbanflet_gold.{tabla}", use_database=False
            )
            if datos["filas"]:
                cliente.insert(
                    tabla, datos["filas"], column_names=datos["columnas"], database=CLICKHOUSE_RESTORE_DB
                )
            conteos[tabla] = len(datos["filas"])

        await _marcar_restauracion_completada(restauracion_id, conteos)
    except Exception as exc:  # noqa: BLE001 -- ver nota de ejecutar_respaldo_mongo
        await _marcar_restauracion_error(restauracion_id, str(exc)[:500])


async def _marcar_restauracion_completada(restauracion_id: str, conteos: dict[str, int]) -> None:
    db = get_mongo_client()[get_settings().mongo_db_name]
    doc = await db.restauraciones.find_one({"_id": restauracion_id})
    ts_fin = datetime.now(UTC)
    duracion = (ts_fin - _como_utc(doc["ts_inicio"])).total_seconds()
    await db.restauraciones.update_one(
        {"_id": restauracion_id},
        {"$set": {"estado": "completado", "ts_fin": ts_fin, "duracion_segundos": duracion, "conteos": conteos}},
    )


async def _marcar_restauracion_error(restauracion_id: str, detalle: str) -> None:
    db = get_mongo_client()[get_settings().mongo_db_name]
    await db.restauraciones.update_one(
        {"_id": restauracion_id},
        {"$set": {"estado": "error", "ts_fin": datetime.now(UTC), "error_detalle": detalle}},
    )


async def listar_restauraciones(db: AsyncIOMotorDatabase, respaldo_id: str | None = None) -> list[dict]:
    filtro = {"respaldo_id": respaldo_id} if respaldo_id else {}
    docs = await db.restauraciones.find(filtro).sort("ts_inicio", -1).to_list(length=100)
    return [restauracion_a_salida(d) for d in docs]


# --- Módulo 7.2: plan de continuidad (DR) -----------------------------------


async def listar_plan_dr(db: AsyncIOMotorDatabase) -> list[dict]:
    guardados = {doc["_id"]: doc async for doc in db.plan_dr.find()}
    return [
        {
            "dominio": dominio,
            "rto": guardados.get(dominio, {}).get("rto", ""),
            "rpo": guardados.get(dominio, {}).get("rpo", ""),
            "notas": guardados.get(dominio, {}).get("notas", ""),
            "actualizado_en": guardados.get(dominio, {}).get("actualizado_en"),
            "actualizado_por": guardados.get(dominio, {}).get("actualizado_por"),
        }
        for dominio in DOMINIOS_DR
    ]


async def actualizar_plan_dr(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, dominio: str, rto: str, rpo: str, notas: str
) -> dict:
    anterior = await db.plan_dr.find_one({"_id": dominio}) or {}
    ahora = datetime.now(UTC)
    nuevo = {"rto": rto, "rpo": rpo, "notas": notas}

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.PLAN_DR_CAMBIO,
        entidad="plan_dr",
        entidad_id=dominio,
        resultado=ResultadoAuditoria.OK,
        datos_previos={"rto": anterior.get("rto", ""), "rpo": anterior.get("rpo", "")},
        datos_posteriores=nuevo,
    )
    await db.plan_dr.update_one(
        {"_id": dominio},
        {"$set": {**nuevo, "actualizado_en": ahora, "actualizado_por": actor_id}},
        upsert=True,
    )
    return {"dominio": dominio, **nuevo, "actualizado_en": ahora, "actualizado_por": actor_id}


async def registrar_simulacro(
    db: AsyncIOMotorDatabase, *, actor_id: str, actor_rol: str, fecha: datetime, resultado: str, notas: str
) -> dict:
    ahora = datetime.now(UTC)
    doc = {
        "_id": str(uuid.uuid4()),
        "fecha": fecha,
        "resultado": resultado,
        "notas": notas,
        "registrado_por": actor_id,
        "registrado_en": ahora,
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=actor_rol,
        accion=AccionAuditoria.SIMULACRO_DR_REGISTRO,
        entidad="simulacros_dr",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"resultado": resultado},
    )
    await db.simulacros_dr.insert_one(doc)
    return doc


async def listar_simulacros(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.simulacros_dr.find().sort("fecha", -1).to_list(length=100)
