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

from src.core.db_clickhouse import fetch_latest_snapshot, get_clickhouse_client

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
