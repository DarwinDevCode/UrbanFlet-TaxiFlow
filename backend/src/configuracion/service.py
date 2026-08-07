"""Parámetros globales del sistema — Módulo 2.1 de admin_sistema
(specs/specs-administrativas/admin_sistema.md). Mismo patrón versionado que
`seguridad/service.py` (política de auth) y `parametros/service.py`
(tarifa/comisión): reutiliza `parametros/service.py::_crear_version`, no
crea un mecanismo paralelo.

`DEFAULTS` son los valores que ya regían fijos en código antes de este
módulo (`viajes/service_dispatch.py::RADIOS_M`/`OFERTA_EXPIRA_SEGUNDOS`) --
el comportamiento del sistema no cambia hasta que un admin_sistema publique
la primera versión real.
"""

from datetime import datetime, UTC

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.parametros.service import ParametroNoVigenteError, _crear_version, obtener_vigente

_TIPO = "sistema"

DEFAULTS = {
    "idioma": "es",
    "zona_horaria": "America/Guayaquil",
    "radios_despacho_m": [300, 600, 1000],
    "oferta_expira_segundos": 20,
}


async def crear_parametro_sistema(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    rol: str,
    idioma: str,
    zona_horaria: str,
    radios_despacho_m: list[int],
    oferta_expira_segundos: int,
    vigente_desde: datetime,
) -> dict:
    from src.core.audit import AccionAuditoria, ResultadoAuditoria, write_audit_event

    anterior = await obtener_parametro_sistema_vigente(db)

    valores = {
        "idioma": idioma,
        "zona_horaria": zona_horaria,
        "radios_despacho_m": radios_despacho_m,
        "oferta_expira_segundos": oferta_expira_segundos,
    }

    # Write-ahead con antes/después, mismo motivo que en seguridad/service.py.
    await write_audit_event(
        db,
        actor_id=actor_id,
        rol=rol,
        accion=AccionAuditoria.PARAMETRO_SISTEMA_CAMBIO,
        entidad="parametro_sistema",
        entidad_id=None,
        resultado=ResultadoAuditoria.OK,
        datos_previos=anterior,
        datos_posteriores={**valores, "vigente_desde": vigente_desde.isoformat()},
    )

    return await _crear_version(
        db, actor_id=actor_id, rol=rol, tipo=_TIPO, valores=valores, vigente_desde=vigente_desde, filtro_serie={}
    )


async def obtener_parametro_sistema_vigente(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    """Nunca lanza -- sin política publicada cae a `DEFAULTS`. Es la función
    que otros módulos (`viajes/service_dispatch.py`) deben llamar para leer
    radios de despacho / expiración de oferta en caliente."""
    try:
        doc = await obtener_vigente(db, tipo=_TIPO, fecha=fecha or datetime.now(UTC))
        return dict(doc["valores"])
    except ParametroNoVigenteError:
        return dict(DEFAULTS)


async def obtener_parametro_sistema_documento(db: AsyncIOMotorDatabase, *, fecha: datetime | None = None) -> dict:
    """Para el endpoint GET -- conserva id/vigencia; sintetiza un documento
    "default" cuando nunca se publicó una versión real."""
    try:
        return await obtener_vigente(db, tipo=_TIPO, fecha=fecha or datetime.now(UTC))
    except ParametroNoVigenteError:
        return {"_id": None, "valores": dict(DEFAULTS), "vigente_desde": None, "vigente_hasta": None}
