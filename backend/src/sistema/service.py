"""Versión desplegada y su historial (Módulo 8.1) + panel de estado de
infraestructura (Módulo 5) de admin_sistema
(specs/specs-administrativas/admin_sistema.md).

**Alcance recortado y APROBADO por el usuario** (ver PLAN_ADMIN_SISTEMA.md,
nota de 8.1): no hay pipeline de CI/CD real en este proyecto (sin GitHub
Actions ni despliegue automatizado documentado en
`arquitectura_software.md`). "Historial de despliegues" se demuestra con
un registro manual (`registro_versiones`, colección nueva) que un
administrador agrega a mano al cerrar una sesión de desarrollo, como dato
consultable desde la UI en vez de vivir solo en `CLAUDE.md` -- no hay
ningún job ni script que lo pueble automáticamente.

**Módulo 5 (Monitoreo) -- alcance recortado y APROBADO por el usuario**
(ver PLAN_ADMIN_SISTEMA.md §16, nota de alcance 5.2): "alertas configurables
por umbral" en producción real implicaría un proceso que sondea
continuamente y dispara notificación -- no hay ningún worker/cron en este
stack apto para eso sin agregar infraestructura nueva (Celery beat, etc.),
desproporcionado para el alcance académico. Se construye la configuración
de umbrales (persistida) y el panel de estado los usa para **colorear**
cada tarjeta (bien/advertencia/crítico) cuando un humano abre el panel --
evaluación bajo demanda, no vigilancia continua ni alerta push automática.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, UTC

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.config import get_settings
from src.core.db_clickhouse import get_clickhouse_client
from src.core.db_redis import get_redis

# Versión de cada frontend -- mantenida a mano en sync con el `version` de
# cada `apps/<app>/package.json`, mismo criterio que `Settings.app_version`
# para el backend (no hay introspección automática: el backend no tiene
# acceso al filesystem de los frontends en producción).
VERSIONES_FRONTEND = {
    "web_pasajero": "0.1.0",
    "web_conductor": "0.1.0",
    "web_interno": "0.1.0",
}


def obtener_version() -> dict:
    return {
        "backend": get_settings().app_version,
        "web_pasajero": VERSIONES_FRONTEND["web_pasajero"],
        "web_conductor": VERSIONES_FRONTEND["web_conductor"],
        "web_interno": VERSIONES_FRONTEND["web_interno"],
    }


async def registrar_despliegue(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, componente: str, version: str, notas: str
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "componente": componente,
        "version": version,
        "notas": notas,
        "desplegado_en": datetime.now(UTC),
        "desplegado_por": actor_id,
    }
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.DESPLIEGUE_REGISTRO,
        entidad="registro_versiones",
        entidad_id=doc["_id"],
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"componente": componente, "version": version},
    )
    await db.registro_versiones.insert_one(doc)
    return doc


async def listar_despliegues(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db.registro_versiones.find().sort("desplegado_en", -1).to_list(length=200)


# --- Módulo 5: panel de estado de infraestructura ---------------------------

COMPONENTES = ("backend", "mongo", "redis", "clickhouse", "airflow")

DEFAULTS_UMBRAL = {
    "backend": {"latencia_advertencia_ms": 500, "latencia_critica_ms": 2000},
    "mongo": {"latencia_advertencia_ms": 200, "latencia_critica_ms": 1000},
    "redis": {"latencia_advertencia_ms": 100, "latencia_critica_ms": 500},
    "clickhouse": {"latencia_advertencia_ms": 500, "latencia_critica_ms": 2000},
    "airflow": {"latencia_advertencia_ms": 1000, "latencia_critica_ms": 3000},
}


async def _medir(componente: str, coro) -> dict:
    """Ejecuta una comprobación real contra `componente` y mide su latencia.

    Nunca propaga el texto crudo de la excepción al llamador -- la nota de
    seguridad de la spec (Módulo 5.1) pide no exponer detalles internos
    (IPs, versiones exactas) a través de este panel; `disponible=False` sin
    detalle es suficiente para el propósito operativo.
    """
    inicio = time.monotonic()
    try:
        await coro
        latencia_ms = round((time.monotonic() - inicio) * 1000, 1)
        return {"componente": componente, "disponible": True, "latencia_ms": latencia_ms}
    except Exception:  # noqa: BLE001 -- ver docstring: se degrada a "no disponible", nunca se filtra el error real
        return {"componente": componente, "disponible": False, "latencia_ms": None}


async def _ping_backend() -> None:
    # El proceso que atiende esta petición ya está vivo por definición --
    # se reporta como una comprobación trivial, no una simulación.
    return None


async def _ping_mongo(db: AsyncIOMotorDatabase) -> None:
    await db.command("ping")


async def _ping_redis() -> None:
    await get_redis().ping()


async def _ping_clickhouse() -> None:
    def _consultar() -> None:
        get_clickhouse_client().query("SELECT 1")

    await asyncio.to_thread(_consultar)


async def _ping_airflow() -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{get_settings().airflow_url}/health")
        resp.raise_for_status()


def _estado(disponible: bool, latencia_ms: float | None, umbral: dict) -> str:
    if not disponible:
        return "critico"
    if latencia_ms is not None and latencia_ms >= umbral["latencia_critica_ms"]:
        return "critico"
    if latencia_ms is not None and latencia_ms >= umbral["latencia_advertencia_ms"]:
        return "advertencia"
    return "bien"


async def obtener_umbrales(db: AsyncIOMotorDatabase) -> dict[str, dict]:
    guardados = {doc["_id"]: doc async for doc in db.umbrales_monitoreo.find()}
    return {
        componente: {
            "latencia_advertencia_ms": guardados.get(componente, {}).get(
                "latencia_advertencia_ms", DEFAULTS_UMBRAL[componente]["latencia_advertencia_ms"]
            ),
            "latencia_critica_ms": guardados.get(componente, {}).get(
                "latencia_critica_ms", DEFAULTS_UMBRAL[componente]["latencia_critica_ms"]
            ),
        }
        for componente in COMPONENTES
    }


async def _registrar_historial(db: AsyncIOMotorDatabase, resultados: list[dict]) -> None:
    """Guarda un snapshot de latencia/estado por componente -- histórico para
    el gráfico de tendencia (punto #6 de la ronda de usabilidad). Se escribe
    en cada consulta real del panel (incl. el auto-refresco de 20s del
    frontend), sin ningún worker/cron nuevo -- el propio uso del panel genera
    la serie de tiempo. Best-effort: un fallo acá nunca debe romper la
    respuesta de /sistema/salud.
    """
    ahora = datetime.now(UTC)
    docs = [
        {"ts": ahora, "componente": r["componente"], "latencia_ms": r["latencia_ms"], "estado": r["estado"]}
        for r in resultados
    ]
    try:
        await db.historial_monitoreo.insert_many(docs)
    except Exception:  # noqa: BLE001 -- telemetría best-effort, ver docstring
        pass


async def obtener_salud(db: AsyncIOMotorDatabase) -> list[dict]:
    umbrales = await obtener_umbrales(db)
    resultados = await asyncio.gather(
        _medir("backend", _ping_backend()),
        _medir("mongo", _ping_mongo(db)),
        _medir("redis", _ping_redis()),
        _medir("clickhouse", _ping_clickhouse()),
        _medir("airflow", _ping_airflow()),
    )
    for r in resultados:
        r["estado"] = _estado(r["disponible"], r["latencia_ms"], umbrales[r["componente"]])
    await _registrar_historial(db, resultados)
    return resultados


async def obtener_historial_latencia(db: AsyncIOMotorDatabase, *, horas: int = 24) -> list[dict]:
    desde = datetime.now(UTC) - timedelta(hours=horas)
    cursor = db.historial_monitoreo.find({"ts": {"$gte": desde}}).sort("ts", 1)
    return await cursor.to_list(length=5000)


# --- Punto #6 de la ronda de usabilidad: indicadores reales de infraestructura ---

async def _indicadores_mongo(db: AsyncIOMotorDatabase) -> dict:
    try:
        status = await db.command("serverStatus")
        stats = await db.command("dbStats")
        conexiones = status.get("connections", {})
        opcounters = status.get("opcounters", {})
        return {
            "disponible": True,
            "conexiones_activas": conexiones.get("current"),
            "conexiones_disponibles": conexiones.get("available"),
            "operaciones_totales": sum(opcounters.values()) if opcounters else None,
            "tamano_datos_mb": round(stats.get("dataSize", 0) / (1024 * 1024), 1),
            "tamano_almacenamiento_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 1),
            "colecciones": stats.get("collections"),
            "indices": stats.get("indexes"),
            "tiempo_actividad_seg": status.get("uptime"),
        }
    except Exception:  # noqa: BLE001 -- ver _medir: se degrada a no disponible, nunca se filtra el error real
        return {"disponible": False}


async def _indicadores_redis() -> dict:
    try:
        info = await get_redis().info()
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return {
            "disponible": True,
            "memoria_usada_mb": round(info.get("used_memory", 0) / (1024 * 1024), 1),
            "clientes_conectados": info.get("connected_clients"),
            "hit_rate_pct": round(hits / total * 100, 1) if total else None,
            "tiempo_actividad_seg": info.get("uptime_in_seconds"),
        }
    except Exception:  # noqa: BLE001
        return {"disponible": False}


async def _indicadores_clickhouse() -> dict:
    def _consultar() -> dict:
        client = get_clickhouse_client()
        consultas = client.query("SELECT value FROM system.metrics WHERE metric = 'Query'").result_rows
        # MemoryResident (RSS real del proceso) -- confirmado contra un ClickHouse
        # real que "MemoryTracking" no existe en system.asynchronous_metrics de
        # esta versión (24.x); MemoryResident sí, y es la memoria real usada.
        memoria = client.query(
            "SELECT value FROM system.asynchronous_metrics WHERE metric = 'MemoryResident'"
        ).result_rows
        uptime = client.query("SELECT uptime()").result_rows
        return {
            "disponible": True,
            "consultas_activas": int(consultas[0][0]) if consultas else None,
            "memoria_usada_mb": round(float(memoria[0][0]) / (1024 * 1024), 1) if memoria else None,
            "tiempo_actividad_seg": int(uptime[0][0]) if uptime else None,
        }

    try:
        return await asyncio.to_thread(_consultar)
    except Exception:  # noqa: BLE001
        return {"disponible": False}


async def obtener_indicadores(db: AsyncIOMotorDatabase) -> dict:
    mongo, redis_, clickhouse = await asyncio.gather(
        _indicadores_mongo(db), _indicadores_redis(), _indicadores_clickhouse()
    )
    return {"mongo": mongo, "redis": redis_, "clickhouse": clickhouse}


async def actualizar_umbral(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    componente: str,
    latencia_advertencia_ms: int,
    latencia_critica_ms: int,
) -> dict:
    anterior = (await obtener_umbrales(db))[componente]
    nuevo = {"latencia_advertencia_ms": latencia_advertencia_ms, "latencia_critica_ms": latencia_critica_ms}

    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.MONITOREO_UMBRAL_CAMBIO,
        entidad="umbrales_monitoreo",
        entidad_id=componente,
        resultado=ResultadoAuditoria.OK,
        datos_previos=anterior,
        datos_posteriores=nuevo,
    )
    await db.umbrales_monitoreo.update_one(
        {"_id": componente}, {"$set": {**nuevo, "actualizado_en": datetime.now(UTC)}}, upsert=True
    )
    return {"componente": componente, **nuevo}


# --- Módulo 8.2b: política de retención vigente por tipo de dato ------------

# Colecciones sin TTL automático: la retención real depende de una decisión
# de negocio/cumplimiento ya documentada en el proyecto, no de un mecanismo
# de Mongo -- se listan aquí en vez de inventar un TTL que no existe.
_RETENCION_DOCUMENTADA = [
    {
        "coleccion": "bitacora",
        "descripcion": "Bitácora de auditoría (CU-O17)",
        "retencion": "Indefinida — requisito de trazabilidad de auditoría, insert-only",
    },
    {
        "coleccion": "viajes / pagos / liquidaciones",
        "descripcion": "Registro operativo y financiero",
        "retencion": "Indefinida — registro contable/operativo de la cooperativa",
    },
    {
        "coleccion": "documentos",
        "descripcion": "Documentación de conductores/vehículos (CU-O01/CU-O17)",
        "retencion": "Vigencia del vínculo con la cooperativa — sin purga automática",
    },
    {
        "coleccion": "usuarios",
        "descripcion": "Datos personales de cuentas (pasajero/conductor/staff)",
        "retencion": "Hasta anonimización manual (Módulo 8.2a) o solicitud ARCO/LOPDP — sin purga automática",
    },
]


async def obtener_politica_retencion(db: AsyncIOMotorDatabase) -> list[dict]:
    politica = list(_RETENCION_DOCUMENTADA)

    ttl_segundos = None
    for info in (await db.posiciones.index_information()).values():
        if "expireAfterSeconds" in info:
            ttl_segundos = info["expireAfterSeconds"]
            break

    retencion_posiciones = (
        f"{ttl_segundos // 86400} días (TTL automático real)" if ttl_segundos else "Sin índice TTL configurado"
    )
    politica.insert(
        0,
        {
            "coleccion": "posiciones",
            "descripcion": "Trazas de ubicación GPS de vehículos en servicio",
            "retencion": retencion_posiciones,
            "fuente": "indice_ttl_real",
        },
    )
    for item in politica[1:]:
        item["fuente"] = "documentado"
    return politica
