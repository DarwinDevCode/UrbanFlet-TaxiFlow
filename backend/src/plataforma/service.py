"""CU-O16 -- lectura del catálogo de indicadores publicados.

Este módulo SOLO lee las tablas de snapshot `rpt_*` en ClickHouse
(urbanflet_gold), publicadas por analytics/plugins/indicadores.py (Airflow,
CU-O15/CU-O16). Nunca consulta tablas transaccionales ni Gold "en vivo" --
ese es justo el punto de CU-O16 paso 3: "los tableros de los jefes de área
consultan exclusivamente estas vistas".

Frescura (A1): cada informe reporta `datos_al` = el `fecha_datos` más
reciente presente en su tabla. Si la corrida del dominio de HOY falló (o no
ha corrido), el refresco de hoy simplemente no insertó filas nuevas (ver
indicadores.py), así que `datos_al` naturalmente queda en el último día
bueno y `retrasado=True` se deriva comparando contra la fecha de hoy -- sin
ninguna lógica adicional aquí.

Selección del snapshot mostrado (A3, swap atómico): el lector NO filtra solo
por `max(fecha_datos)` -- `fecha_datos` tiene granularidad de día, así que
dos refrescos el mismo día (p. ej. el DAG horario de flota, o una
regeneración manual A2 seguida del refresco normal del DAG) compartirían el
mismo `fecha_datos` y sus filas se mezclarían en una sola consulta. En su
lugar se filtra por `max(actualizado_en)`, que es único por llamada a
`indicadores.refrescar_*` (un solo `datetime.utcnow()` por refresco, igual
para todas las filas de ese INSERT) -- así se selecciona exactamente el
conjunto de filas de UN refresco, nunca una mezcla de dos.
"""

from __future__ import annotations

from datetime import date

from src.core.agregacion_estrategica import agrupar, variacion_pct
from src.core.db_clickhouse import fetch_latest_snapshot, fetch_snapshot_history, get_clickhouse_client

# (id_informe, nombre_visible, tabla)
_CATALOGO: list[tuple[str, str, str]] = [
    ("flota_activa_franja", "% de flota activa por franja", "rpt_flota_activa_franja"),
    ("tasa_discrepancias", "Tasa de discrepancias", "rpt_tasa_discrepancias"),
    ("margen_comision", "Margen de comisión", "rpt_margen_comision"),
    ("conversion_onboarding", "Conversión de onboarding", "rpt_conversion_onboarding"),
    ("documentacion_vigente", "Documentación vigente por tipo", "rpt_documentacion_vigente"),
    ("uso_integraciones", "Uso de integraciones por endpoint", "rpt_uso_integraciones"),
]


def _snapshot_informe(client, id_informe: str, nombre: str, tabla: str) -> dict:
    try:
        max_rows = client.query(f"SELECT max(actualizado_en) FROM {tabla}").result_rows
    except Exception:  # noqa: BLE001 -- cualquier error de ClickHouse (tabla ausente, red) degrada igual
        # Tabla todavía no creada (ningún DAG de CU-O16 corrió aún) --
        # se sirve como informe vacío y retrasado, nunca un error 500: el
        # consumidor debe poder ver el catálogo aunque un dominio nunca haya
        # publicado nada todavía.
        return {"id": id_informe, "nombre": nombre, "datos_al": None, "retrasado": True, "filas": []}

    actualizado_en = max_rows[0][0] if max_rows else None
    if actualizado_en is None:
        return {"id": id_informe, "nombre": nombre, "datos_al": None, "retrasado": True, "filas": []}

    resultado = client.query(
        f"SELECT * FROM {tabla} WHERE actualizado_en = {{actualizado_en:DateTime}}",
        parameters={"actualizado_en": actualizado_en},
    )
    filas = [dict(zip(resultado.column_names, fila, strict=True)) for fila in resultado.result_rows]

    fecha_datos = filas[0]["fecha_datos"] if filas else None
    for fila in filas:
        fila.pop("fecha_datos", None)
        if "actualizado_en" in fila:
            fila["actualizado_en"] = fila["actualizado_en"].isoformat()

    # Excepción justificada en la auditoría de orden de tablas: acá NO aplica
    # "más reciente primero" -- la consulta filtra por UN `actualizado_en`
    # exacto, así que todas las filas del informe son del mismo instante de
    # publicación y no hay recencia que las distinga. Lo que sí faltaba era
    # determinismo: sin `ORDER BY`, ClickHouse podía devolver las mismas
    # filas en distinto orden entre consultas. Se ordena por las columnas
    # dimensionales del propio informe (las que quedan tras quitar la
    # metadata), que es genérico y no exige conocer cada tabla `rpt_*`.
    if filas:
        dimensiones = [c for c in filas[0] if c != "actualizado_en"]
        filas.sort(key=lambda f: tuple(str(f.get(c, "")) for c in dimensiones))

    retrasado = fecha_datos != date.today() if fecha_datos is not None else True
    return {"id": id_informe, "nombre": nombre, "datos_al": fecha_datos, "retrasado": retrasado, "filas": filas}


def obtener_catalogo_indicadores() -> list[dict]:
    client = get_clickhouse_client()
    try:
        return [_snapshot_informe(client, id_informe, nombre, tabla) for id_informe, nombre, tabla in _CATALOGO]
    finally:
        client.close()


def listar_corridas(*, dominio: str | None = None, fecha_logica: date | None = None, limite: int = 50) -> list[dict]:
    """Panel táctico de Plataforma -- CU-T14/OT8.1, informe simple.

    Lee directo de `corridas` (ClickHouse) -- decisión del usuario, ver
    docstring de `schemas.CorridaOut`."""
    client = get_clickhouse_client()
    try:
        condiciones = []
        parametros: dict = {}
        if dominio:
            condiciones.append("dag_id = {dominio:String}")
            parametros["dominio"] = dominio
        if fecha_logica:
            condiciones.append("fecha_logica = {fecha_logica:Date}")
            parametros["fecha_logica"] = fecha_logica
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        resultado = client.query(
            f"""
            SELECT dag_id, fecha_logica, estado, registros_extraidos, registros_cuarentena,
                   iniciado_en, finalizado_en
            FROM urbanflet_gold.corridas
            {where}
            ORDER BY iniciado_en DESC
            LIMIT {int(limite)}
            """,
            parameters=parametros,
        )
        filas = [dict(zip(resultado.column_names, fila, strict=True)) for fila in resultado.result_rows]
        for fila in filas:
            extraidos = fila["registros_extraidos"]
            fila["pct_cuarentena"] = fila["registros_cuarentena"] / extraidos if extraidos > 0 else 0.0
        return filas
    finally:
        client.close()


def obtener_cuarentena_dominio() -> list[dict]:
    """Informe compuesto (ClickHouse) del panel táctico de Plataforma -- CU-T14/OT8.1."""
    client = get_clickhouse_client()
    try:
        filas = fetch_latest_snapshot(client, "rpt_cuarentena_dominio")
    finally:
        client.close()
    return sorted(filas, key=lambda f: f["dag_id"])


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Capacidades y Plataforma
# (OE3, nivel_estrategico.md §3.3, patrón Z)
# ---------------------------------------------------------------------------


def obtener_panel_capacidades(*, cortes: int = 12) -> dict:
    """Segunda capa de agregación sobre `rpt_cuarentena_dominio`, sin tabla nueva.

    `rpt_cuarentena_dominio` no tiene dimensión de periodo propia (es un corte
    por corrida), así que la tendencia sale de `fetch_snapshot_history` sobre
    `fecha_datos` -- caso 2 de `core/agregacion_estrategica`.

    "Corridas OK vs. fallidas del periodo" se cuenta directo sobre la tabla
    `corridas` de ClickHouse, la misma fuente que ya usa `listar_corridas`
    (informe simple del panel táctico de Plataforma) -- sigue siendo
    ClickHouse, no Mongo, así que no rompe la regla de la Sección 2 de la
    spec estratégica.

    **Acotado a la ventana `cortes` (Tier 1 de la auditoría, hallazgo H-T3):**
    antes esta query no tenía ningún filtro de fecha -- contaba el histórico
    completo de la tabla `corridas` pese a que el frontend la etiqueta "en el
    periodo". `corridas` no es una `rpt_*` con `fecha_datos` propia (es un
    log de eventos, una fila por corrida real de un DAG), así que no hay un
    "corte" propio que traducir 1:1 -- se interpreta cada unidad de `cortes`
    como un día calendario sobre `corridas.iniciado_en`, mismo eje de tiempo
    que ya usa `listar_corridas` del panel táctico. Con esto la etiqueta "en
    el periodo" queda veraz sin cambiar el texto.

    **"Avance de capacitación por área" va siempre en `None`**: no existe
    ningún dominio de capacitación en el sistema (backlog consciente ya
    documentado en el nivel táctico). Se declara
    `capacitacion_disponible=false` en metadata en vez de fabricar el dato.
    """
    client = get_clickhouse_client()
    try:
        actual = fetch_latest_snapshot(client, "rpt_cuarentena_dominio")
        historial = fetch_snapshot_history(client, "rpt_cuarentena_dominio", limite_dias=cortes)
        corridas = client.query(
            """
            SELECT estado, count() AS total
            FROM urbanflet_gold.corridas
            WHERE iniciado_en >= now() - INTERVAL {cortes:UInt32} DAY
            GROUP BY estado
            """,
            parameters={"cortes": cortes},
        ).result_rows
    finally:
        client.close()

    por_estado = {str(estado): int(total) for estado, total in corridas}
    corridas_ok = por_estado.get("OK", 0) + por_estado.get("WARN", 0)
    corridas_fallidas = sum(v for k, v in por_estado.items() if k not in ("OK", "WARN"))

    def _pct_global(filas: list[dict]) -> float | None:
        extraidos = sum(f["registros_extraidos"] for f in filas)
        if not extraidos:
            return None
        return round(sum(f["registros_cuarentena"] for f in filas) / extraidos, 4)

    tendencia = [
        {
            "periodo": str(fecha),
            "pct_cuarentena": _pct_global(filas) or 0.0,
            "registros_extraidos": sum(f["registros_extraidos"] for f in filas),
            "registros_cuarentena": sum(f["registros_cuarentena"] for f in filas),
        }
        for fecha, filas in sorted(agrupar(historial, "fecha_datos").items())
    ]

    dominios = sorted(
        (
            {
                "dag_id": f["dag_id"],
                "pct_cuarentena": f["pct_cuarentena"],
                "registros_extraidos": f["registros_extraidos"],
                "registros_cuarentena": f["registros_cuarentena"],
            }
            for f in actual
        ),
        key=lambda f: f["pct_cuarentena"],
        reverse=True,
    )

    pct_actual = tendencia[-1]["pct_cuarentena"] if tendencia else None
    pct_previo = tendencia[-2]["pct_cuarentena"] if len(tendencia) > 1 else None
    # Tier 1, punto 6 (H-T5): `pct_cuarentena` es un promedio ponderado por
    # `registros_extraidos` -- el n real del periodo anterior es ese peso.
    registros_previos_cuarentena = (
        tendencia[-2]["registros_extraidos"] if len(tendencia) > 1 else None
    )

    return {
        "kpis": {
            "pct_cuarentena_global": pct_actual,
            "variacion_cuarentena_pct": variacion_pct(pct_actual, pct_previo),
            "dominio_mas_afectado": dominios[0]["dag_id"] if dominios else None,
            "corridas_ok": corridas_ok,
            "corridas_fallidas": corridas_fallidas,
            "avance_capacitacion_pct": None,  # ver docstring
        },
        "tendencia_cuarentena": tendencia,
        "dominios": dominios,
        "metadata": {
            "cortes": cortes,
            "capacitacion_disponible": False,
            "fuentes": ["rpt_cuarentena_dominio", "corridas"],
            "registros_previos": {"variacion_cuarentena_pct": registros_previos_cuarentena},
        },
    }
