"""Parámetros versionados — PARAMETRO_TARIFA / PARAMETRO_COMISION / ZONA
(diseno_base_datos.md §1.4-1.5). "Ningún valor de negocio va cableado en
código" (arquitectura_software.md línea 121): toda tarifa/comisión se lee por
fecha de vigencia, nunca de una constante.

Cache en memoria del backend (línea 149 de diseno_base_datos.md) con TTL corto:
son pocos documentos que cambian con poca frecuencia, así que no vale la pena
ir a Mongo en cada cálculo de tarifa de cada viaje.
"""

import time
import uuid
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event
from src.core.exceptions import DomainError

_CACHE_TTL_SECONDS = 30
_cache: dict[str, tuple[float, dict | None]] = {}


class ParametroNoVigenteError(DomainError):
    def __init__(self, tipo: str) -> None:
        super().__init__(
            code="PARAMETRO_NO_VIGENTE",
            message=f"No hay un parámetro de tipo '{tipo}' vigente para la fecha solicitada",
            status_code=409,
        )


def _cache_key(tipo: str, extra: str | None, fecha: datetime) -> str:
    return f"{tipo}:{extra}:{fecha.date().isoformat()}"


async def _crear_version(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    tipo: str,
    valores: dict,
    vigente_desde: datetime,
    filtro_serie: dict,
) -> dict:
    # Write-ahead: se registra la intención de cambio antes de tocar el estado.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.PARAMETRO_CAMBIO,
        entidad="parametros",
        entidad_id=None,
        resultado=ResultadoAuditoria.OK,
        datos_posteriores={"tipo": tipo, **valores, "vigente_desde": vigente_desde.isoformat()},
    )

    # Cierra la versión previa abierta de la misma serie, si existe, para que
    # nunca haya dos versiones vigentes solapadas.
    await db.parametros.update_many(
        {**filtro_serie, "tipo": tipo, "vigente_hasta": None},
        {"$set": {"vigente_hasta": vigente_desde}},
    )

    documento = {
        "_id": str(uuid.uuid4()),
        "tipo": tipo,
        **filtro_serie,
        "valores": valores,
        "vigente_desde": vigente_desde,
        "vigente_hasta": None,
    }
    await db.parametros.insert_one(documento)
    _cache.clear()
    return documento


async def crear_parametro_tarifa(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    franja: str,
    arrancada: float,
    costo_km: float,
    costo_min_espera: float,
    carrera_minima: float,
    vigente_desde: datetime,
) -> dict:
    valores = {
        "arrancada": arrancada,
        "costo_km": costo_km,
        "costo_min_espera": costo_min_espera,
        "carrera_minima": carrera_minima,
    }
    return await _crear_version(
        db,
        actor_id=actor_id,
        rol=rol,
        tipo="tarifa",
        valores=valores,
        vigente_desde=vigente_desde,
        filtro_serie={"franja": franja},
    )


async def crear_parametro_comision(
    db: AsyncIOMotorDatabase, *, actor_id: str, rol: str, porcentaje: float, vigente_desde: datetime
) -> dict:
    return await _crear_version(
        db,
        actor_id=actor_id,
        rol=rol,
        tipo="comision",
        valores={"porcentaje": porcentaje},
        vigente_desde=vigente_desde,
        filtro_serie={},
    )


async def obtener_vigente(db: AsyncIOMotorDatabase, *, tipo: str, fecha: datetime, franja: str | None = None) -> dict:
    key = _cache_key(tipo, franja, fecha)
    cached = _cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        if cached[1] is None:
            raise ParametroNoVigenteError(tipo)
        return cached[1]

    filtro: dict = {"tipo": tipo, "vigente_desde": {"$lte": fecha}}
    filtro["$or"] = [{"vigente_hasta": None}, {"vigente_hasta": {"$gt": fecha}}]
    if franja is not None:
        filtro["franja"] = franja

    documento = await db.parametros.find_one(filtro, sort=[("vigente_desde", -1)])
    _cache[key] = (time.monotonic(), documento)
    if documento is None:
        raise ParametroNoVigenteError(tipo)
    return documento


async def listar_historial(db: AsyncIOMotorDatabase, *, tipo: str, franja: str | None = None) -> list[dict]:
    """Todas las versiones de una serie (`tipo` + `franja` para tarifa, solo
    `tipo` para comisión, que no se particiona por franja), más recientes
    primero -- fuente de verdad para auditar cómo cambió un parámetro de
    dinero a lo largo del tiempo, no solo cuál rige hoy."""
    filtro: dict = {"tipo": tipo}
    if franja is not None:
        filtro["franja"] = franja
    return await db.parametros.find(filtro, sort=[("vigente_desde", -1)]).to_list(length=200)


