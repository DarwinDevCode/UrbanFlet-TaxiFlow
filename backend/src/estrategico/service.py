"""Los 2 dashboards estratégicos que NO pertenecen a un solo dominio.

Por qué existe este módulo (y por qué los otros 7 dashboards estratégicos no
viven acá): el nivel táctico ya decidió, explícitamente, no tener un módulo
central — cada dominio expone sus propios `GET /<dominio>/panel-tactico/...`.
Esa decisión se mantiene: 7 de los 9 dashboards estratégicos tienen un
dominio dueño claro y viven en el router de ese dominio.

Los 2 que quedan acá no lo tienen, y forzarlos dentro de un dominio sería
arbitrario:

- **Panel de Rentabilidad y Demanda (OE4 / CU-E02+CU-E03)** cruza 4 dominios
  a la vez (finanzas, mantenimiento, despacho y flota) para calcular un
  margen que no es de ninguno de ellos en particular.
- **Tablero Ejecutivo Consolidado (CU-E01)** cruza los 8 dashboards
  anteriores por definición — es un índice, no un dashboard de dominio.

No es un módulo central "porque sí": si mañana se agrega un dashboard
estratégico con dominio dueño, va en el router de su dominio, no acá.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.agregacion_estrategica import agrupar, promedio_ponderado, ultimos_periodos, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client

LOGGER = logging.getLogger(__name__)

# Reparto de cada bucket horario de 6h de `rpt_flota_activa_franja`
# (00-06 / 06-12 / 12-18 / 18-24) sobre la franja tarifaria real del negocio
# (DIURNA / NOCTURNA). La franja DIURNA está definida en
# `core/config.py::franja_diurna_desde_hora/hasta_hora` como 05:00-22:00 hora
# local, así que el reparto es aritmética exacta de horas dentro de cada
# bucket, no una estimación: 00-06 tiene 1 hora diurna (05-06) de 6; 18-24
# tiene 4 (18-22) de 6; los dos buckets del medio son 100% diurnos.
#
# Hace falta porque las dos tablas `rpt_*` que este panel cruza usan
# taxonomías distintas de "franja": `rpt_tiempo_asignacion` publica
# DIURNA/NOCTURNA (el campo real del viaje) y `rpt_flota_activa_franja`
# publica buckets de 6h derivados de la hora del ping GPS.
FRACCION_DIURNA_POR_BUCKET = {
    "00-06": 1 / 6,
    "06-12": 1.0,
    "12-18": 1.0,
    "18-24": 4 / 6,
}

FRANJAS = ("DIURNA", "NOCTURNA")


def _share_demanda_por_franja(asignacion: list[dict]) -> dict[str, float]:
    """Participación de cada franja en la demanda atendida del último corte.

    Fuente: `rpt_tiempo_asignacion.total_registros` (viajes con asignación
    real), que ya viene desglosado por franja DIURNA/NOCTURNA."""
    totales = {
        franja: sum(f["total_registros"] for f in filas)
        for franja, filas in agrupar(asignacion, "franja").items()
        if franja in FRANJAS
    }
    universo = sum(totales.values())
    if not universo:
        return {}
    return {franja: totales.get(franja, 0) / universo for franja in FRANJAS}


def _share_capacidad_por_franja(flota: list[dict]) -> dict[str, float]:
    """Participación de cada franja en la capacidad de flota expuesta.

    "Capacidad expuesta" = registros de posición con el vehículo disponible
    (`total_registros * pct_disponible`) del bucket horario, repartido a
    DIURNA/NOCTURNA con `FRACCION_DIURNA_POR_BUCKET`."""
    diurna = 0.0
    nocturna = 0.0
    for fila in flota:
        expuesta = float(fila["total_registros"]) * float(fila["pct_disponible"])
        fraccion = FRACCION_DIURNA_POR_BUCKET.get(str(fila["franja"]))
        if fraccion is None:
            continue
        diurna += expuesta * fraccion
        nocturna += expuesta * (1 - fraccion)
    universo = diurna + nocturna
    if not universo:
        return {}
    return {"DIURNA": diurna / universo, "NOCTURNA": nocturna / universo}


def obtener_panel_rentabilidad(*, meses: int = 12) -> dict:
    """Panel de Rentabilidad y Demanda — OE4 / CU-E02 + CU-E03, patrón F.

    ── FÓRMULA DE MARGEN (decisión de diseño de esta fase) ─────────────────

    Ni la spec estratégica (§3.4) ni ninguna sesión anterior definieron con
    precisión "recaudación  -  comisión  -  costo de mantenimiento prorrateado".
    La fórmula que este endpoint implementa, y su justificación, quedan acá
    como constancia — mismo criterio que otras interpretaciones ya
    documentadas del proyecto (p. ej. "retención a 90 días" en Captación).

    Para cada mes `m` y cada franja `f` ∈ {DIURNA, NOCTURNA}:

        recaudacion[m][f] = bruto_total[m]       *  share_demanda[f]
        comision[m][f]    = comisiones_total[m]  *  share_demanda[f]
        costo_mant[m][f]  = costo_mant_total[m]  *  share_capacidad[f]
        margen[m][f]      = recaudacion  -  comision  -  costo_mant
        margen_pct[m][f]  = margen / recaudacion

    donde:
      · `bruto_total[m]` / `comisiones_total[m]` salen de `rpt_margen_comision`
        (Finanzas), que ya publica ambos por mes.
      · `costo_mant_total[m]` es la suma de `rpt_costo_mantenimiento_vehiculo`
        (Mantenimiento) para ese mes, sobre todos los vehículos.
      · `share_demanda[f]` sale de `rpt_tiempo_asignacion` (Despacho).
      · `share_capacidad[f]` sale de `rpt_flota_activa_franja` (Flota).

    **Por qué DOS bases de prorrateo distintas y no una sola.** Prorratear
    los tres componentes por la misma participación daría un `margen_pct`
    idéntico en todas las franjas — matemáticamente cierto y analíticamente
    inútil, porque el dashboard existe justamente para comparar franjas. La
    distinción tiene sustento de negocio real: la recaudación y la comisión
    escalan con los **viajes efectivamente atendidos**, mientras que el costo
    de mantenimiento escala con la **exposición del activo** (un vehículo en
    servicio se desgasta esté ocupado o no). Así, una franja con mucha flota
    disponible y poca demanda sale con margen menor — exactamente la señal
    que las decisiones de CU-E02 (dónde reforzar flota) y CU-E03 (ajuste
    tarifario) necesitan.

    **Limitaciones declaradas en `metadata`, no disimuladas:**
      · `zona_disponible=false` — `viajes.zona_origen_id` sigue sin resolverse
        (0 de 1.3M documentos), así que la matriz es mes  *  franja y no
        zona  *  franja como pide la spec. Alcance recortado que la propia
        spec ya previó.
      · `demanda_viajes_disponible=false` — la "tendencia de demanda de largo
        plazo" se sirve como recaudación bruta por trimestre
        (`rpt_margen_comision`), no como conteo de viajes solicitados por
        mes: ninguna vista `rpt_*` publica ese conteo (ver la misma
        limitación en el Panel de Crecimiento).
      · `share_demanda`/`share_capacidad` provienen del ÚLTIMO corte
        publicado y se aplican a todos los meses de la ventana — las 2
        tablas de origen no tienen dimensión de periodo propia. Es una
        aproximación: si el reparto por franja cambió mucho en el tiempo, los
        meses viejos lo reflejarán con el mix actual.
    """
    client = get_clickhouse_client()
    try:
        margen_rpt = fetch_latest_snapshot(client, "rpt_margen_comision")
        costos = fetch_latest_snapshot(client, "rpt_costo_mantenimiento_vehiculo")
        asignacion = fetch_latest_snapshot(client, "rpt_tiempo_asignacion")
        flota = fetch_latest_snapshot(client, "rpt_flota_activa_franja")
    finally:
        client.close()

    share_demanda = _share_demanda_por_franja(asignacion)
    share_capacidad = _share_capacidad_por_franja(flota)

    periodos = ultimos_periodos([f["periodo"] for f in margen_rpt], meses)
    por_periodo_margen = agrupar(margen_rpt, "periodo")
    costo_por_periodo = {
        periodo: sum(f["costo_total"] for f in filas)
        for periodo, filas in agrupar(costos, "periodo").items()
    }

    matriz: list[dict] = []
    for periodo in periodos:
        filas = por_periodo_margen.get(periodo, [])
        bruto = sum(f["bruto_total"] for f in filas)
        comisiones = sum(f["comisiones_total"] for f in filas)
        costo_mant = costo_por_periodo.get(periodo, 0.0)
        for franja in FRANJAS:
            sd = share_demanda.get(franja, 0.0)
            sc = share_capacidad.get(franja, 0.0)
            recaudacion = bruto * sd
            comision = comisiones * sd
            costo = costo_mant * sc
            margen = recaudacion - comision - costo
            matriz.append(
                {
                    "periodo": periodo,
                    "franja": franja,
                    "recaudacion": round(recaudacion, 2),
                    "comision": round(comision, 2),
                    "costo_mantenimiento": round(costo, 2),
                    "margen": round(margen, 2),
                    "margen_pct": round(margen / recaudacion, 4) if recaudacion else None,
                    "share_demanda": round(sd, 4),
                    "share_capacidad": round(sc, 4),
                }
            )

    # Consolidado por franja sobre toda la ventana (los KPIs del panel).
    resumen_franja = []
    for franja, filas in agrupar(matriz, "franja").items():
        recaudacion = sum(f["recaudacion"] for f in filas)
        margen = sum(f["margen"] for f in filas)
        resumen_franja.append(
            {
                "franja": franja,
                "recaudacion": round(recaudacion, 2),
                "comision": round(sum(f["comision"] for f in filas), 2),
                "costo_mantenimiento": round(sum(f["costo_mantenimiento"] for f in filas), 2),
                "margen": round(margen, 2),
                "margen_pct": round(margen / recaudacion, 4) if recaudacion else None,
            }
        )
    resumen_franja.sort(key=lambda f: f["margen_pct"] if f["margen_pct"] is not None else 1.0)

    # Tendencia de demanda de largo plazo, por trimestre (proxy: recaudación
    # bruta -- ver limitación `demanda_viajes_disponible` del docstring).
    por_trimestre: dict[str, dict] = {}
    for periodo in periodos:
        anio, mes = periodo.split("-")[0], int(periodo.split("-")[1])
        clave = f"{anio}-T{(mes - 1) // 3 + 1}"
        acc = por_trimestre.setdefault(clave, {"periodo": clave, "recaudacion": 0.0, "meses": 0})
        acc["recaudacion"] += sum(f["bruto_total"] for f in por_periodo_margen.get(periodo, []))
        acc["meses"] += 1
    tendencia_demanda = [
        {"periodo": k, "recaudacion": round(v["recaudacion"], 2), "meses": v["meses"]}
        for k, v in sorted(por_trimestre.items())
    ]

    margen_actual = tendencia_demanda[-1]["recaudacion"] if tendencia_demanda else None
    margen_previo = tendencia_demanda[-2]["recaudacion"] if len(tendencia_demanda) > 1 else None

    margen_promedio = promedio_ponderado(resumen_franja, "margen_pct", "recaudacion")

    return {
        "kpis": {
            "margen_promedio_pct": margen_promedio,
            "franja_menos_rentable": resumen_franja[0]["franja"] if resumen_franja else None,
            "margen_menos_rentable_pct": resumen_franja[0]["margen_pct"] if resumen_franja else None,
            "recaudacion_ultimo_trimestre": margen_actual,
            "variacion_recaudacion_trimestral_pct": variacion_pct(margen_actual, margen_previo),
        },
        "matriz": matriz,
        "resumen_franja": resumen_franja,
        "tendencia_demanda": tendencia_demanda,
        "metadata": {
            "meses": meses,
            "zona_disponible": False,
            "demanda_viajes_disponible": False,
            "formula": (
                "margen[mes][franja] = bruto_total * share_demanda  -  comisiones * share_demanda "
                " -  costo_mantenimiento * share_capacidad. Ver docstring de "
                "estrategico/service.py::obtener_panel_rentabilidad."
            ),
            "fuentes": [
                "rpt_margen_comision",
                "rpt_costo_mantenimiento_vehiculo",
                "rpt_tiempo_asignacion",
                "rpt_flota_activa_franja",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Tablero Ejecutivo Consolidado — CU-E01 (nivel_estrategico.md §4)
# ---------------------------------------------------------------------------

# Decisión de diseño: el backend devuelve los 8 headlines en UNA sola
# respuesta, en vez de dejar que el frontend haga 8 llamadas. Razones: (a) el
# tablero es un índice de navegación, se abre entero o no se abre; (b) los 8
# dashboards ya están gateados por rol y `gerencia` es el único rol que la
# spec lista para los 8, así que una respuesta única no filtra nada que el
# actor no pudiera pedir por separado; (c) evita 8 handshakes y 8 clientes
# ClickHouse abiertos desde el navegador en el primer render.
#
# El enlace "Ver detalle" de cada tarjeta (spec §4) NO necesita nada del
# backend: es navegación entre secciones del frontend (Fase 4).

# `seccion` es el identificador que el frontend usará para resolver a qué
# panel estratégico navega cada tarjeta -- se define acá para que el mapeo
# tarjeta→destino tenga una sola fuente de verdad y no un mirror manual en
# TSX (mismo problema ya resuelto en Auditoría Administrativa con
# `GET /auditoria/acciones-administrativas`).
_HEADLINES = (
    ("crecimiento", "Crecimiento", "Conversión de onboarding", "OE1"),
    ("confiabilidad", "Confiabilidad del servicio", "Flota activa promedio", "OE2"),
    ("estado-costo-flota", "Costo de flota", "Cumplimiento del plan preventivo", "OE2"),
    ("capacidades", "Capacidades y plataforma", "Cuarentena del pipeline", "OE3"),
    ("rentabilidad", "Rentabilidad", "Margen promedio", "OE4"),
    ("integridad-financiera", "Integridad financiera", "Conciliación", "OE5"),
    ("cumplimiento-normativo", "Cumplimiento normativo", "Documentación vigente", "OE6"),
    ("gobernanza", "Gobernanza de datos", "Eventos administrativos del periodo", "OE6"),
)


def _tarjeta(seccion: str, valor, unidad: str, variacion, tendencia: list[dict]) -> dict:
    meta = next(h for h in _HEADLINES if h[0] == seccion)
    return {
        "seccion": seccion,
        "titulo": meta[1],
        "kpi": meta[2],
        "objetivo": meta[3],
        "valor": valor,
        "unidad": unidad,
        "variacion_pct": variacion,
        "tendencia": tendencia,
        "disponible": valor is not None,
    }


async def obtener_tablero_ejecutivo(db: AsyncIOMotorDatabase) -> dict:
    """CU-E01: un KPI headline por cada uno de los 8 dashboards estratégicos.

    Cada headline se resuelve llamando al mismo servicio que sirve su
    dashboard de detalle — nunca reimplementando el cálculo, para que el
    número del tablero y el del panel no puedan divergir.

    Cada bloque va en su propio `try`: si una fuente `rpt_*` está vacía o
    ClickHouse no responde, esa tarjeta sale con `disponible=false` y el
    tablero se sirve igual — un índice de navegación no debe caerse entero
    por un dominio sin datos.
    """
    from src.auditoria import service as auditoria_service
    from src.captacion import service as captacion_service
    from src.cumplimiento import service as cumplimiento_service
    from src.mantenimiento import service as mantenimiento_service
    from src.plataforma import service as plataforma_service
    from src.recaudacion import service as recaudacion_service
    from src.viajes import service as viajes_service

    tarjetas: list[dict] = []

    def _mini(puntos: list[dict], campo: str) -> list[dict]:
        return [{"periodo": p["periodo"], "valor": p[campo]} for p in puntos[-6:]]

    async def _agregar(seccion: str, unidad: str, cargar):
        try:
            valor, variacion, tendencia = await cargar()
        except Exception:  # una fuente caída no tumba el tablero entero
            LOGGER.warning("tablero_ejecutivo: headline '%s' no disponible", seccion, exc_info=True)
            valor, variacion, tendencia = None, None, []
        tarjetas.append(_tarjeta(seccion, valor, unidad, variacion, tendencia))

    async def _crecimiento():
        d = captacion_service.obtener_panel_crecimiento()
        return (
            d["kpis"]["pct_conversion_onboarding"],
            d["kpis"]["variacion_altas_pct"],
            _mini(d["tendencia_onboarding"], "pct_activo"),
        )

    async def _confiabilidad():
        d = viajes_service.obtener_panel_confiabilidad()
        return d["kpis"]["pct_flota_activa"], None, _mini(d["tendencia_flota"], "pct_disponible")

    async def _flota():
        d = await mantenimiento_service.obtener_panel_estado_costo_flota(db)
        return (
            d["kpis"]["pct_cumplimiento_preventivo"],
            d["kpis"]["variacion_cumplimiento_pct"],
            _mini(d["tendencia_preventivo"], "pct_cumplimiento"),
        )

    async def _capacidades():
        d = plataforma_service.obtener_panel_capacidades()
        return (
            d["kpis"]["pct_cuarentena_global"],
            d["kpis"]["variacion_cuarentena_pct"],
            _mini(d["tendencia_cuarentena"], "pct_cuarentena"),
        )

    async def _rentabilidad():
        d = obtener_panel_rentabilidad()
        return (
            d["kpis"]["margen_promedio_pct"],
            d["kpis"]["variacion_recaudacion_trimestral_pct"],
            _mini(d["tendencia_demanda"], "recaudacion"),
        )

    async def _financiera():
        d = recaudacion_service.obtener_panel_integridad_financiera()
        return (
            d["kpis"]["pct_conciliado"],
            d["kpis"]["variacion_conciliado_pct"],
            _mini(d["tendencia_conciliacion"], "pct_conciliado"),
        )

    async def _normativo():
        d = cumplimiento_service.obtener_panel_cumplimiento_normativo()
        return (
            d["kpis"]["pct_vigente"],
            d["kpis"]["variacion_vigencia_pct"],
            _mini(d["tendencia_vigencia"], "pct_vigente"),
        )

    async def _gobernanza():
        d = await auditoria_service.obtener_gobernanza_datos(db, limite_eventos=1)
        return (
            d["kpis"]["eventos_administrativos"],
            d["kpis"]["variacion_accesos_denegados_pct"],
            _mini(d["tendencia"], "eventos_administrativos"),
        )

    await _agregar("crecimiento", "porcentaje", _crecimiento)
    await _agregar("confiabilidad", "porcentaje", _confiabilidad)
    await _agregar("estado-costo-flota", "porcentaje", _flota)
    await _agregar("capacidades", "porcentaje", _capacidades)
    await _agregar("rentabilidad", "porcentaje", _rentabilidad)
    await _agregar("integridad-financiera", "porcentaje", _financiera)
    await _agregar("cumplimiento-normativo", "porcentaje", _normativo)
    await _agregar("gobernanza", "conteo", _gobernanza)

    return {
        "tarjetas": tarjetas,
        "metadata": {
            "total": len(tarjetas),
            "disponibles": sum(1 for t in tarjetas if t["disponible"]),
        },
    }
