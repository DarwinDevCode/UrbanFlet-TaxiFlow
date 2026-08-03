"""Cliente ClickHouse compartido para lectores de nivel táctico (Gold/rpt_*).

Mismo patrón que originalmente vivía solo en `plataforma/service.py` (CU-O16):
sin autenticación contra el contenedor `clickhouse` de docker-compose.yml, el
mismo cliente que usa `analytics/plugins/medallion.py`. Se comparte aquí
porque cada dominio (flota, mantenimiento, finanzas...) necesita leer sus
propias tablas `rpt_*` para sus dashboards tácticos, no solo `plataforma`.
"""

from __future__ import annotations

import clickhouse_connect

from src.core.config import get_settings


def get_clickhouse_client():
    settings = get_settings()
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host, port=settings.clickhouse_port, database=settings.clickhouse_db
    )


def fetch_latest_snapshot(client, tabla: str) -> list[dict]:
    """Última corrida publicada de una tabla `rpt_*`, o `[]` si aún no existe/no ha corrido.

    Filtra por `max(actualizado_en)` (único por refresco), no por `fecha_datos`
    (varias corridas del mismo día -- p. ej. flota, horaria -- comparten
    `fecha_datos`), siguiendo el mismo razonamiento que
    `plataforma/service.py::_snapshot_informe`.
    """
    try:
        max_rows = client.query(f"SELECT max(actualizado_en) FROM {tabla}").result_rows
    except Exception:  # noqa: BLE001 -- tabla ausente / ClickHouse caído: se sirve vacío, nunca 500
        return []

    actualizado_en = max_rows[0][0] if max_rows else None
    if actualizado_en is None:
        return []

    resultado = client.query(
        f"SELECT * FROM {tabla} WHERE actualizado_en = {{actualizado_en:DateTime}}",
        parameters={"actualizado_en": actualizado_en},
    )
    filas = [dict(zip(resultado.column_names, fila, strict=True)) for fila in resultado.result_rows]
    for fila in filas:
        if "actualizado_en" in fila:
            fila["actualizado_en"] = fila["actualizado_en"].isoformat()
        if "fecha_datos" in fila and hasattr(fila["fecha_datos"], "isoformat"):
            fila["fecha_datos"] = fila["fecha_datos"].isoformat()
    return filas


def fetch_snapshot_history(client, tabla: str, limite_dias: int = 6) -> list[dict]:
    """Últimos N `fecha_datos` distintos de una tabla `rpt_*` (append-only), más recientes primero.

    Para informes de "tendencia" que necesitan varios puntos en el tiempo en
    vez de solo el último snapshot -- sin tabla nueva, aprovechando que las
    tablas `rpt_*` son MergeTree (no Replacing) y conservan historial.
    """
    try:
        fechas_rows = client.query(
            f"SELECT DISTINCT fecha_datos FROM {tabla} ORDER BY fecha_datos DESC LIMIT {int(limite_dias)}"
        ).result_rows
    except Exception:  # noqa: BLE001
        return []
    if not fechas_rows:
        return []
    fechas = [row[0] for row in fechas_rows]

    resultado = client.query(
        f"""
        SELECT t.* FROM {tabla} t
        INNER JOIN (
            SELECT fecha_datos, max(actualizado_en) AS actualizado_en
            FROM {tabla}
            WHERE fecha_datos IN {{fechas:Array(Date)}}
            GROUP BY fecha_datos
        ) ult ON t.fecha_datos = ult.fecha_datos AND t.actualizado_en = ult.actualizado_en
        ORDER BY t.fecha_datos DESC
        """,
        parameters={"fechas": fechas},
    )
    filas = [dict(zip(resultado.column_names, fila, strict=True)) for fila in resultado.result_rows]
    for fila in filas:
        if "actualizado_en" in fila:
            fila["actualizado_en"] = fila["actualizado_en"].isoformat()
        if "fecha_datos" in fila and hasattr(fila["fecha_datos"], "isoformat"):
            fila["fecha_datos"] = fila["fecha_datos"].isoformat()
    return filas
