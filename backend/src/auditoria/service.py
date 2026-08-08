"""Agregaciones de nivel estratégico sobre la bitácora de auditoría.

Panel de Gobernanza de Datos y Seguridad (OE6b / CU-E05,
`specs/nivel-estrategico/nivel_estrategico.md` §3.6.b, patrón F).

Excepción documentada a la regla de la Sección 2 de la spec estratégica
("ningún informe estratégico se consulta directo de MongoDB, siempre sobre
`rpt_*`"): la bitácora **no tiene ninguna tabla `rpt_*` detrás** — el nivel
táctico de Auditoría (Módulo 6.1 de Administración) también la lee directo
de `bitacora`, y la propia spec estratégica declara como fuente de este
dashboard "los eventos de auditoría administrativa ya construidos (Módulo
6.1), agregados a nivel de tendencia", no una vista `rpt_*`. La regla se
respeta en los otros 7 dashboards, que sí tienen `rpt_*` como fuente.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.audit import ACCIONES_ADMINISTRATIVAS, AccionAuditoria

# "Alertas de seguridad" del periodo: eventos de seguridad que NO son un
# acceso denegado suelto (ese tiene su propio KPI y su propia tendencia, no
# se cuenta dos veces).
ACCIONES_ALERTA_SEGURIDAD = (
    AccionAuditoria.LOGIN_FALLIDO_CONSECUTIVO.value,
    AccionAuditoria.POSIBLE_GPS_SPOOFING.value,
)

_ACCIONES_ADMIN = sorted(a.value for a in ACCIONES_ADMINISTRATIVAS)


def _inicio_ventana(meses: int) -> datetime:
    """Inicio de la ventana de análisis, en UTC aware.

    Se calcula siempre a partir de `datetime.now(UTC)` y se compara contra
    `bitacora.ts`, que Mongo devuelve naive — pero acá nunca se resta un
    valor leído contra uno generado: el rango va como filtro dentro del
    query, donde el driver serializa ambos a BSON UTC sin ambigüedad."""
    return datetime.now(UTC) - timedelta(days=30 * meses)


async def _contar(db: AsyncIOMotorDatabase, filtro: dict) -> int:
    return await db.bitacora.count_documents(filtro)


async def _tendencia_mensual(db: AsyncIOMotorDatabase, desde: datetime) -> list[dict]:
    """Conteo por mes de las 3 familias de evento que mira este dashboard.

    El agrupado por mes se hace en Python y no con `$dateToString` en un
    `aggregate` a propósito: la proyección trae solo `ts`/`accion` de la
    ventana pedida (unos miles de documentos en el peor caso real de este
    entorno), y el pipeline de agregación con operadores de fecha no está
    soportado por el doble de Mongo que usan los tests (`mongomock_motor`)."""
    accion_admin = set(_ACCIONES_ADMIN)
    accion_alerta = set(ACCIONES_ALERTA_SEGURIDAD)
    por_periodo: dict[str, dict] = {}

    cursor = db.bitacora.find({"ts": {"$gte": desde}}, {"ts": 1, "accion": 1})
    async for doc in cursor:
        periodo = doc["ts"].strftime("%Y-%m")
        fila = por_periodo.setdefault(
            periodo,
            {"periodo": periodo, "eventos_administrativos": 0, "accesos_denegados": 0, "alertas_seguridad": 0},
        )
        accion = doc.get("accion")
        if accion in accion_admin:
            fila["eventos_administrativos"] += 1
        if accion == AccionAuditoria.ACCESO_DENEGADO.value:
            fila["accesos_denegados"] += 1
        if accion in accion_alerta:
            fila["alertas_seguridad"] += 1

    return [por_periodo[k] for k in sorted(por_periodo)]


async def obtener_gobernanza_datos(
    db: AsyncIOMotorDatabase, *, meses: int = 6, limite_eventos: int = 100
) -> dict:
    """Panel de Gobernanza de Datos y Seguridad (OE6b, patrón F).

    KPIs del periodo + tendencia mensual + la tabla dominante de eventos
    administrativos consolidados (el elemento visual principal del patrón F,
    igual que la bitácora en el dashboard táctico de Auditoría).
    """
    desde = _inicio_ventana(meses)
    inicio_previo = _inicio_ventana(meses * 2)

    filtro_admin = {"accion": {"$in": _ACCIONES_ADMIN}, "ts": {"$gte": desde}}
    filtro_denegados = {"accion": AccionAuditoria.ACCESO_DENEGADO.value, "ts": {"$gte": desde}}
    filtro_alertas = {"accion": {"$in": list(ACCIONES_ALERTA_SEGURIDAD)}, "ts": {"$gte": desde}}
    filtro_denegados_previos = {
        "accion": AccionAuditoria.ACCESO_DENEGADO.value,
        "ts": {"$gte": inicio_previo, "$lt": desde},
    }

    eventos_admin = await _contar(db, filtro_admin)
    denegados = await _contar(db, filtro_denegados)
    alertas = await _contar(db, filtro_alertas)
    denegados_previos = await _contar(db, filtro_denegados_previos)

    variacion = None
    if denegados_previos:
        variacion = round((denegados - denegados_previos) / denegados_previos * 100, 2)

    cursor = db.bitacora.find(filtro_admin).sort("evento_id", -1).limit(limite_eventos)
    eventos = [doc async for doc in cursor]

    return {
        "kpis": {
            "eventos_administrativos": eventos_admin,
            "accesos_denegados": denegados,
            "alertas_seguridad": alertas,
            "variacion_accesos_denegados_pct": variacion,
        },
        "tendencia": await _tendencia_mensual(db, desde),
        "eventos": eventos,
        "metadata": {
            "meses": meses,
            "desde": desde,
            "fuente": "bitacora (Mongo) — sin rpt_* detrás, ver docstring del módulo",
        },
    }
